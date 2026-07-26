import logging
from langchain_core.messages import HumanMessage, SystemMessage
from utils.constants import llm, available_paths, MASTER_EMAIL
from schemas import AgentState
from utils.loader import load_prompt

logger = logging.getLogger(__name__)


def _keyword_route(query: str) -> str | None:
    normalized = query.casefold()

    music_keywords = (
        "music",
        "song",
        "songs",
        "album",
        "albums",
        "artist",
        "artists",
        "playlist",
        "spotify",
        "listen",
        "taste",
    )
    if any(keyword in normalized for keyword in music_keywords):
        return "music"

    movie_keywords = (
        "movie",
        "movies",
        "film",
        "films",
        "watch",
        "cinema",
        "letterboxd",
        "genre",
    )
    if any(keyword in normalized for keyword in movie_keywords):
        return "movie"

    return None


def router_agent(state: AgentState) -> AgentState:
    query = state["messages"][-1].content

    paths = dict(available_paths)
    if state['email'] == MASTER_EMAIL:
        paths["master"] = (
            "Use this path for privileged or administrative actions such as managing Nenad Kajgana’s CD collection, "
            "updating ownership, or performing database and Pinecone operations."
        )

    keyword_decision = _keyword_route(query)
    if keyword_decision and keyword_decision in paths:
        state["next_step"] = keyword_decision
        return state

    paths_description = "\n".join(f"- {k}: {v}" for k, v in paths.items())
    keys_list = ", ".join(paths.keys())

    routing_prompt = load_prompt(
        "route",
        context={
            "paths": paths_description,
            "keys": keys_list,
            "query": query,
            "convo_history": state["convo_history"]
        }
    )

    response = llm.invoke([
        SystemMessage(content=routing_prompt),
        HumanMessage(content=query)
    ])

    decision = response.content.strip().lower()
    state["next_step"] = decision if decision in paths else "main"
    return state
