import logging
from typing import cast

from langchain_core.messages import HumanMessage
from graphs.user_chat import create_graph, AgentState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run(user_query: str, convo_history:str='') -> AgentState:
    """
    Run the agent graph with a user query.

    Args:
        user_query: The user's question

    Returns:
        The final AgentState with the assistant's response
    """
    logger.info(f"Starting agent with query: {user_query}")

    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_query)],
        "context": "",
        "next_step": "route",
        "convo_history": convo_history
    }

    graph = create_graph()

    final_state = cast(AgentState, graph.invoke(initial_state))

    final_answer = (
        final_state["messages"][-1].content
        if final_state["messages"]
        else ""
    )

    logger.info(f"Agent completed. Answer: {final_answer[:100]}...")

    return final_state


def main():
    """
    Main entry point. Reads queries from stdin and runs the agent.
    """
    print("=" * 80)
    print("Nenad Kajgana's AI Assistant — Router-Enhanced Workflow")
    print("=" * 80)

    try:
        while True:
            # user_input = input("Ask anything about Nenad: \n")
            user_input = "Give me some music album suggestions"
            if not user_input:
                continue

            final_state = run(user_input)

            print(f"\nAssistant: {final_state['messages'][-1].content}\n")
            print("-" * 80)

    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
    except Exception as e:
        logger.exception("Unhandled error in main loop: %s", e)


if __name__ == "__main__":
    main()
