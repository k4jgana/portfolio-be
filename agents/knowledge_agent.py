import logging
from langchain_core.messages import HumanMessage
from tools.index import retrieve_context
from utils.constants import llm
from schemas import AgentState
from utils.loader import load_prompt

logger = logging.getLogger(__name__)

def knowledge_agent(state: AgentState) -> AgentState:
    query = state["messages"][-1].content
    logger.info(f"[KnowledgeAgent] Retrieving knowledge for: {query}")

    retrieved = retrieve_context.invoke({"query": query})
    logger.debug(f"[KnowledgeAgent] Retrieved {len(retrieved) if isinstance(retrieved, str) else 0} characters of context")

    summary_prompt = load_prompt(
        "knowledge",
        context={
            "retrieved": retrieved,
            "query": query
        }
    )

    response = llm.invoke([HumanMessage(content=summary_prompt)])
    state["context"] = response.content

    logger.info("[KnowledgeAgent] Knowledge processed, returning to main_agent")
    return state
