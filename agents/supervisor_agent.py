from functools import partial
from typing import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool

from schemas import AgentState
from utils.loader import load_prompt


def supervisor_agent(
    state: AgentState,
    *,
    model_with_tools: BaseChatModel,
) -> dict:
    """Choose any needed capabilities, then produce the single final answer."""
    prompt = load_prompt(
        "supervisor",
        context={"convo_history": state.get("convo_history", "")},
    )
    response = model_with_tools.invoke(
        [SystemMessage(content=prompt), *state["messages"]]
    )
    return {"messages": [response]}


def build_supervisor_node(model: BaseChatModel, tools: Sequence[BaseTool]):
    """Bind a fixed authorization-specific tool set to the supervisor."""
    model_with_tools = model.bind_tools(list(tools))
    return partial(supervisor_agent, model_with_tools=model_with_tools)
