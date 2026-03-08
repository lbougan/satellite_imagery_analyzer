"""LangGraph agent state schema."""

from typing import Annotated
import operator
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    aoi_geojson: dict | None
    imagery_results: Annotated[list[dict], operator.add]
