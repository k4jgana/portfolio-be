import logging
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from utils.constants import llm
from schemas import AgentState
from utils.loader import load_prompt

logger = logging.getLogger(__name__)

def main_agent(state: AgentState) -> AgentState:
    context = state.get("context", "")
    convo_history = state.get("convo_history", "")
    if not context:
        state["next_step"] = "route"
        return state

    query = state["messages"][-1].content

    answer_prompt = load_prompt(
        "main",
        context={
            "context": context or "[NONE]",
            "query": query,
            "convo_history": convo_history,
        }
    )

    response = llm.invoke([
        SystemMessage(content=answer_prompt),
        *state["messages"]
    ])

    state["messages"].append(AIMessage(content=response.content))
    state["next_step"] = "end"
    return state
