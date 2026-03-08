"""LangGraph agent graph definition."""

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.agent.nodes import inject_system_message
from app.agent.tools.search_imagery import search_imagery
from app.agent.tools.download_imagery import download_imagery, download_imagery_batch
from app.agent.tools.compute_index import compute_index
from app.agent.tools.analyze_image import analyze_image
from app.agent.tools.compare_images import compare_images
from app.config import get_settings

ALL_TOOLS = [search_imagery, download_imagery, download_imagery_batch, compute_index, analyze_image, compare_images]


def _should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph():
    settings = get_settings()

    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
        streaming=True,
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def call_model(state: AgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("inject_system", inject_system_message)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("inject_system")
    graph.add_edge("inject_system", "agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()
