import logging
from langgraph.graph import StateGraph
from agents.knowledge_agent import knowledge_agent
from agents.main_agent import main_agent
from agents.movie_recc_agent import movie_recommendations_agent
from agents.router_agent import router_agent
from agents.music_recc_agent import music_recommendations_agent
from agents.master_controller_agent import master_controller_agent
from schemas import AgentState
from utils.constants import MASTER_EMAIL

logger = logging.getLogger(__name__)

def create_graph(user_email: str):
    """
    Dynamically builds the agent graph depending on who the user is.
    Master email gets privileged 'master_controller_agent'.
    """
    workflow = StateGraph(AgentState)

    # Core agents
    workflow.add_node("main_agent", main_agent)
    workflow.add_node("router_agent", router_agent)
    workflow.add_node("knowledge_agent", knowledge_agent)
    workflow.add_node("music_recommendations_agent", music_recommendations_agent)
    workflow.add_node("movie_recommendations_agent", movie_recommendations_agent)
    workflow.set_entry_point("router_agent")

    routing_map = {
        "knowledge": "knowledge_agent",
        "main": "main_agent",
        "music": "music_recommendations_agent",
        "movie": "movie_recommendations_agent",
    }

    if user_email == MASTER_EMAIL:
        workflow.add_node("master_controller_agent", master_controller_agent)
        routing_map["master"] = "master_controller_agent"

    workflow.add_conditional_edges(
        "router_agent",
        lambda state: state["next_step"],
        routing_map
    )

    # Return routes
    workflow.add_edge("knowledge_agent", "main_agent")
    workflow.add_edge("music_recommendations_agent", "main_agent")
    workflow.add_edge("movie_recommendations_agent", "main_agent")

    if user_email == MASTER_EMAIL:
        workflow.add_edge("master_controller_agent", "main_agent")

    return workflow.compile()
