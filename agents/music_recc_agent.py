import logging

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from tools.spotify import (
    get_album_recommendations,
    get_artist_recommendations,
    get_song_recommendations,
)
from tools.master_tools import get_cd_collection
from utils.constants import llm
from utils.loader import load_prompt
from schemas import AgentState
from langchain.agents import create_agent

logger = logging.getLogger(__name__)


def music_recommendations_agent(state: AgentState) -> AgentState:
    """
    Agent that processes user queries about music and uses Spotify tools
    via a React agent to return recommendations.
    """
    llm_with_tools = llm.bind_tools(
        [get_album_recommendations, get_artist_recommendations, get_song_recommendations, get_cd_collection]
    )
    query = state["messages"][-1].content
    logger.info(f"[MusicAgent] Received query: {query!r}")
    system_prompt = load_prompt("music", context={"query": query})

    music_agent = create_agent(
        model=llm_with_tools,
        tools=[get_album_recommendations, get_artist_recommendations, get_song_recommendations, get_cd_collection],
    )
    input_messages = [SystemMessage(content=system_prompt), HumanMessage(content=query)]
    response = music_agent.invoke({"messages": input_messages})

    content = response['messages'][-1].content
    try:
        assistant_msg = AIMessage(content=content)
        state["messages"].append(assistant_msg)
    except Exception:
        logger.debug("Could not append AIMessage to state['messages']", exc_info=True)

    state["context"] = content

    logger.info("[MusicAgent] Recommendations processed, returning to main agent")
    return state
