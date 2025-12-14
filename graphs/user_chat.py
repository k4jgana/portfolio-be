import logging
from langgraph.graph import StateGraph, END, START

from agents.knowledge_agent import knowledge_agent
from agents.main_agent import main_agent
from agents.movie_recc_agent import movie_recommendations_agent
from agents.router_agent import router_agent
from agents.music_recc_agent import music_recommendations_agent

from schemas import AgentState

logger = logging.getLogger(__name__)

def create_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("main_agent", main_agent)
    workflow.add_node("router_agent", router_agent)
    workflow.add_node("knowledge_agent", knowledge_agent)
    workflow.add_node("music_recommendations_agent", music_recommendations_agent)
    workflow.add_node("movie_recommendations_agent", movie_recommendations_agent)


    workflow.set_entry_point("router_agent")

    # # After main_agent finishes phase 1 → go to router
    # workflow.add_conditional_edges(
    #     "main_agent",
    #     lambda state: state["next_step"],
    #     {"route": "router_agent", "end": END}
    # )

    # Router decides the next worker agent
    workflow.add_conditional_edges(
        "router_agent",
        lambda state: state["next_step"],
        {
            "knowledge": "knowledge_agent",
            "main": "main_agent",
            "music":"music_recommendations_agent",
            "movie": "movie_recommendations_agent"
        }
    )

    workflow.add_edge("knowledge_agent", "main_agent")
    workflow.add_edge("music_recommendations_agent", "main_agent")
    workflow.add_edge("movie_recommendations_agent", "main_agent")

    return workflow.compile()
