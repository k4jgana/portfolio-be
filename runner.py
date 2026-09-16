import logging
from typing import cast

from langchain_core.messages import AIMessage, HumanMessage

from graphs.user_chat import get_admin_graph, get_guest_graph
from schemas import AgentState

logger = logging.getLogger(__name__)


def run(
    user_query: str,
    convo_history: str = "",
    is_admin: bool = False,
) -> AIMessage:
    """Run the cached authorization-specific graph and return its final answer."""
    logger.info("Starting supervisor for query=%r admin=%s", user_query, is_admin)
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_query)],
        "convo_history": convo_history,
    }
    graph = get_admin_graph() if is_admin else get_guest_graph()
    final_state = cast(AgentState, graph.invoke(initial_state))

    if not final_state["messages"] or not isinstance(final_state["messages"][-1], AIMessage):
        raise RuntimeError("The assistant workflow did not produce a final response.")
    final_message = cast(AIMessage, final_state["messages"][-1])
    if final_message.tool_calls:
        raise RuntimeError("The assistant workflow stopped before completing its response.")

    logger.info("Supervisor completed with %s response characters", len(str(final_message.content)))
    return final_message


def main() -> None:
    print("Nenad Kajgana's AI Assistant — LangGraph Supervisor")
    try:
        while True:
            user_input = input("Ask anything about Nenad: \n").strip()
            if not user_input:
                continue
            print(f"\nAssistant: {run(user_input).content}\n")
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")


if __name__ == "__main__":
    main()
