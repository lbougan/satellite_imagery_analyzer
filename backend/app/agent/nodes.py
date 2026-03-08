"""LangGraph node functions."""

from datetime import date
from langchain_core.messages import SystemMessage
from app.agent.state import AgentState
from app.agent.prompts import SYSTEM_PROMPT_TEMPLATE


def inject_system_message(state: AgentState) -> AgentState:
    """Prepend system prompt (with current date) and AOI context if not already present."""
    messages = state["messages"]
    if messages and isinstance(messages[0], SystemMessage):
        return state

    today = date.today().isoformat()
    system_parts = [SYSTEM_PROMPT_TEMPLATE.format(today=today)]
    aoi = state.get("aoi_geojson")
    if aoi:
        system_parts.append(
            f"\n\nThe user has selected an Area of Interest (AOI):\n```json\n{aoi}\n```\n"
            "Use the AOI bounding box for imagery searches. "
            "Also pass this bbox to `download_imagery` to clip the download."
        )

    return {
        "messages": [SystemMessage(content="\n".join(system_parts))] + messages,
        "aoi_geojson": state.get("aoi_geojson"),
        "imagery_results": [],
    }
