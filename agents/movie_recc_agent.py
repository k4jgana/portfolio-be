import logging

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from tools.letterboxd import (
    get_recent_movie_ratings,
    get_genre_recommendations,
    get_personal_picks,
get_movie_ratings_by_year
)
from utils.constants import llm
from utils.loader import load_prompt
from schemas import AgentState
from langchain.agents import create_agent

logger = logging.getLogger(__name__)


def movie_recommendations_agent(state: AgentState) -> AgentState:
    """
    Agent that processes user queries about movies and uses Letterboxd tools
    via a React agent to return recommendations.
    """
    llm_with_tools = llm.bind_tools(
        [get_recent_movie_ratings, get_genre_recommendations, get_personal_picks, get_movie_ratings_by_year]
    )
    query = state["messages"][-1].content
    logger.info(f"[MovieAgent] Received query: {query!r}")
    system_prompt = load_prompt("movie", context={"query": query})

    movie_agent = create_agent(
        model=llm_with_tools,
        tools=[get_recent_movie_ratings, get_genre_recommendations, get_personal_picks,get_movie_ratings_by_year],
    )
    input_messages = [SystemMessage(content=system_prompt), HumanMessage(content=query)]
    response = movie_agent.invoke({"messages": input_messages})

    content = response['messages'][-1].content
    try:
        assistant_msg = AIMessage(content=content)
        state["messages"].append(assistant_msg)
    except Exception:
        logger.debug("Could not append AIMessage to state['messages']", exc_info=True)

    state["context"] = content

    logger.info("[MovieAgent] Recommendations processed, returning to main agent")
    return state
