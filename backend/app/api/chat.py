"""WebSocket chat endpoint with LangGraph agent streaming."""

import asyncio
import json
import traceback
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.database import async_session
from app.models import Conversation, Message
from app.agent.graph import build_graph

router = APIRouter()

_graph = None
_running_tasks: dict[str, asyncio.Task] = {}


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _extract_imagery_refs(text: str) -> list[str]:
    """Pull out filenames like *.png from agent text."""
    import re
    return re.findall(r"[\w\-]+\.png", text)


def cancel_running_agent(conversation_id: str):
    """Cancel a running agent task for a conversation. Safe to call from anywhere."""
    task = _running_tasks.pop(conversation_id, None)
    if task and not task.done():
        task.cancel()


async def _handle_agent_run(
    websocket: WebSocket,
    conversation_id: str,
    user_content: str,
    aoi_geojson: dict | None,
):
    """Run the agent graph, stream events over WS, and persist the result."""
    graph = _get_graph()
    initial_state = {
        "messages": [HumanMessage(content=user_content)],
        "aoi_geojson": aoi_geojson,
        "imagery_results": [],
    }

    full_response = ""
    imagery_files: list[str] = []
    was_cancelled = False
    _needs_paragraph_break = False

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    raw_content = chunk.content
                    text = ""
                    if isinstance(raw_content, str):
                        text = raw_content
                    elif isinstance(raw_content, list):
                        text = "".join(
                            block.get("text", "") for block in raw_content
                            if isinstance(block, dict) and block.get("type") == "text"
                        )
                    if text:
                        if _needs_paragraph_break:
                            full_response += "\n\n"
                            await websocket.send_json({
                                "type": "token",
                                "content": "\n\n",
                            })
                            _needs_paragraph_break = False
                        full_response += text
                        await websocket.send_json({
                            "type": "token",
                            "content": text,
                        })

            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                await websocket.send_json({
                    "type": "tool_start",
                    "tool": tool_name,
                    "content": f"Running {tool_name}...",
                })

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                output = event.get("data", {}).get("output", "")
                if hasattr(output, "content"):
                    output_str = output.content if isinstance(output.content, str) else str(output.content)
                elif isinstance(output, str):
                    output_str = output
                else:
                    output_str = str(output)

                refs = _extract_imagery_refs(output_str)
                imagery_files.extend(refs)

                await websocket.send_json({
                    "type": "tool_end",
                    "tool": tool_name,
                    "content": output_str,
                    "imagery_files": refs,
                })
                _needs_paragraph_break = True

    except asyncio.CancelledError:
        was_cancelled = True
    except Exception as e:
        error_msg = f"Agent error: {str(e)}"
        full_response = error_msg
        try:
            await websocket.send_json({"type": "error", "content": error_msg})
        except Exception:
            pass
        traceback.print_exc()
    finally:
        _running_tasks.pop(conversation_id, None)

    imagery_files.extend(_extract_imagery_refs(full_response))
    unique_imagery = list(set(imagery_files))

    try:
        async with async_session() as db:
            assistant_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response if full_response else "(Stopped by user)",
                metadata_json={"imagery_files": unique_imagery} if unique_imagery else None,
            )
            db.add(assistant_msg)

            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            if conv and conv.title == "New Conversation" and user_content:
                conv.title = user_content[:80]
            await db.commit()
    except Exception:
        traceback.print_exc()

    try:
        if was_cancelled:
            await websocket.send_json({
                "type": "stopped",
                "content": full_response,
                "imagery_files": unique_imagery,
            })
        else:
            await websocket.send_json({
                "type": "done",
                "content": full_response,
                "imagery_files": unique_imagery,
            })
    except Exception:
        pass


@router.websocket("/ws/chat/{conversation_id}")
async def chat_websocket(websocket: WebSocket, conversation_id: str):
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("action") == "stop":
                task = _running_tasks.get(conversation_id)
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                else:
                    try:
                        await websocket.send_json({"type": "stopped", "content": ""})
                    except Exception:
                        pass
                continue

            user_content = data.get("content", "")
            aoi_geojson = data.get("aoi_geojson")

            existing = _running_tasks.get(conversation_id)
            if existing and not existing.done():
                existing.cancel()
                try:
                    await existing
                except (asyncio.CancelledError, Exception):
                    pass

            async with async_session() as db:
                result = await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conv = result.scalar_one_or_none()
                if not conv:
                    await websocket.send_json({"type": "error", "content": "Conversation not found"})
                    continue

                user_msg = Message(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_content,
                    metadata_json={"aoi_geojson": aoi_geojson} if aoi_geojson else None,
                )
                db.add(user_msg)
                await db.commit()

            await websocket.send_json({"type": "status", "content": "Agent is thinking..."})

            task = asyncio.create_task(
                _handle_agent_run(websocket, conversation_id, user_content, aoi_geojson)
            )
            _running_tasks[conversation_id] = task

    except WebSocketDisconnect:
        cancel_running_agent(conversation_id)
    except Exception as e:
        cancel_running_agent(conversation_id)
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
