import logging
from langchain_core.messages import HumanMessage, SystemMessage
from utils.constants import llm, available_paths, MASTER_EMAIL
from schemas import AgentState
from utils.loader import load_prompt

logger = logging.getLogger(__name__)

def router_agent(state: AgentState) -> AgentState:
    query = state["messages"][-1].content

    if state['email']== MASTER_EMAIL:
        available_paths["master"] = (
            "Use this path for privileged or administrative actions such as managing Nenad Kajgana’s CD collection, "
            "updating ownership, or performing database and Pinecone operations."
        )

    paths_description = "\n".join(f"- {k}: {v}" for k, v in available_paths.items())
    keys_list = ", ".join(available_paths.keys())

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
    state["next_step"] = decision if decision in available_paths else "main"
    return state