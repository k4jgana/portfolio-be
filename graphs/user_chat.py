from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import RetryPolicy

from agents.supervisor_agent import build_supervisor_node
from graphs.checkpointing import get_checkpointer
from schemas import AgentState
from tools.index import search_nenad_knowledge
from tools.letterboxd import retrieve_movie_context
from tools.master_tools import propose_admin_change
from tools.spotify import retrieve_music_context
from utils.constants import get_llm

READ_ONLY_TOOLS: tuple[BaseTool, ...] = (
    search_nenad_knowledge,
    retrieve_music_context,
    retrieve_movie_context,
)
ADMIN_TOOLS: tuple[BaseTool, ...] = (
    *READ_ONLY_TOOLS,
    propose_admin_change,
)


def _next_node(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


@lru_cache(maxsize=2)
def create_graph(is_admin: bool = False):
    """Compile and cache a graph with a fixed, authorization-safe allowlist."""
    allowed_tools = ADMIN_TOOLS if is_admin else READ_ONLY_TOOLS
    workflow = StateGraph(AgentState)
    workflow.add_node(
        "supervisor",
        build_supervisor_node(get_llm(), allowed_tools),
        retry_policy=RetryPolicy(max_attempts=2),
    )
    workflow.add_node("tools", ToolNode(list(allowed_tools), handle_tool_errors=True))
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        _next_node,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "supervisor")
    return workflow.compile(checkpointer=get_checkpointer())


def get_guest_graph():
    return create_graph(False)


def get_admin_graph():
    return create_graph(True)
