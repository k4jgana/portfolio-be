from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from agents.supervisor_agent import build_supervisor_node
from schemas import AgentState
from tools.index import search_nenad_knowledge
from tools.letterboxd import retrieve_movie_context
from tools.master_tools import add_new_cd, update_cd_have_status, upsert_record
from tools.spotify import retrieve_music_context
from utils.constants import llm

READ_ONLY_TOOLS: tuple[BaseTool, ...] = (
    search_nenad_knowledge,
    retrieve_music_context,
    retrieve_movie_context,
)
ADMIN_TOOLS: tuple[BaseTool, ...] = (
    *READ_ONLY_TOOLS,
    add_new_cd,
    update_cd_have_status,
    upsert_record,
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
    workflow.add_node("supervisor", build_supervisor_node(llm, allowed_tools))
    workflow.add_node("tools", ToolNode(list(allowed_tools)))
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        _next_node,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "supervisor")
    return workflow.compile()


def get_guest_graph():
    return create_graph(False)


def get_admin_graph():
    return create_graph(True)
