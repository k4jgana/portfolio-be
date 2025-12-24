import logging
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain.agents import create_agent

from tools.master_tools import (
    get_cd_collection,
    add_new_cd,
    update_cd_have_status,
    upsert_record
)
from services.cd_service import get_cds
from utils.constants import llm, MASTER_EMAIL
from utils.loader import load_prompt
from schemas import AgentState

logger = logging.getLogger(__name__)


def master_controller_agent(state: AgentState) -> AgentState:
    """
    Master Controller Agent:
    Handles privileged operations like CD management (and later, Pinecone inserts).
    Only available if the user email matches MASTER_EMAIL.
    """
    user_email = state.get("email")
    query = state["messages"][-1].content
    CDs = get_cds()

    if user_email != MASTER_EMAIL:
        logger.warning(f"[MasterController] Unauthorized access attempt by {user_email}")
        state["messages"].append(
            AIMessage(content="Unauthorized: You do not have permission to perform master operations.")
        )
        state["next_step"] = "main"
        return state

    logger.info(f"[MasterController] Activated by {user_email} with query: {query!r}")
    tools = [get_cd_collection, add_new_cd, update_cd_have_status, upsert_record]
    llm_with_tools = llm.bind_tools(tools)
    system_prompt = load_prompt("master", context={"query": query, "cds": CDs})

    master_agent = create_agent(
        model=llm_with_tools,
        tools=tools,
    )

    # Compose the messages
    input_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query)
    ]

    try:
        response = master_agent.invoke({"messages": input_messages})
        content = response["messages"][-1].content
    except Exception as e:
        logger.error(f"[MasterController] Error: {e}", exc_info=True)
        content = "An error occurred while executing master command."

    # Save output to state
    state["messages"].append(AIMessage(content=content))
    state["context"] = content
    state["next_step"] = "main"

    logger.info("[MasterController] Finished and returned to main agent")
    return state
