import json
import logging
from dataclasses import dataclass
from typing import Iterable, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from graphs.user_chat import get_admin_graph, get_guest_graph
from schemas import AgentState, AdminActionProposal

logger = logging.getLogger(__name__)

GRAPH_RECURSION_LIMIT = 8


@dataclass(frozen=True)
class AgentRunResult:
    message: AIMessage
    pending_proposal: AdminActionProposal | None = None
    proposal_summary: str | None = None


def _pending_proposal(messages: Iterable[BaseMessage]) -> tuple[AdminActionProposal | None, str | None]:
    proposals: list[tuple[AdminActionProposal, str]] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name != "propose_admin_change":
            continue
        try:
            content = message.content
            payload = json.loads(content) if isinstance(content, str) else content
            if payload.get("status") != "pending_confirmation":
                continue
            proposals.append((AdminActionProposal.model_validate(payload["proposal"]), payload["summary"]))
        except (TypeError, ValueError, KeyError):
            logger.warning("Ignoring malformed admin proposal tool response.")
    if len(proposals) > 1:
        raise RuntimeError("The assistant proposed more than one protected change in one request.")
    return proposals[0] if proposals else (None, None)


def run(
    user_query: str,
    *,
    chat_session_id: str,
    history_messages: list[BaseMessage] | None = None,
    is_admin: bool = False,
) -> AgentRunResult:
    """Run the authorization-specific graph using a stable conversation thread."""
    logger.info("Starting supervisor admin=%s session=%s", is_admin, chat_session_id)
    graph = get_admin_graph() if is_admin else get_guest_graph()
    config = {
        "configurable": {"thread_id": chat_session_id},
        "recursion_limit": GRAPH_RECURSION_LIMIT,
    }

    initial_messages: list[BaseMessage] = [HumanMessage(content=user_query)]
    # On a first checkpointed request, retain legacy persisted turns. Once a
    # checkpoint exists, passing only the new message prevents duplication.
    try:
        snapshot = graph.get_state(config)
        if not snapshot.values.get("messages") and history_messages:
            initial_messages = [*history_messages, *initial_messages]
    except Exception:
        # SQLite fallback and old compiled graphs continue to use relational
        # history without making a chat request fail.
        if history_messages:
            initial_messages = [*history_messages, *initial_messages]

    initial_state: AgentState = {"messages": initial_messages}
    try:
        final_state = cast(AgentState, graph.invoke(initial_state, config=config))
    except GraphRecursionError as exc:
        raise RuntimeError("The assistant exceeded its tool-use limit. Please try a narrower request.") from exc

    if not final_state["messages"] or not isinstance(final_state["messages"][-1], AIMessage):
        raise RuntimeError("The assistant workflow did not produce a final response.")
    final_message = cast(AIMessage, final_state["messages"][-1])
    if final_message.tool_calls:
        raise RuntimeError("The assistant workflow stopped before completing its response.")

    proposal, summary = _pending_proposal(final_state["messages"])
    logger.info("Supervisor completed response_chars=%s proposal=%s", len(str(final_message.content)), bool(proposal))
    return AgentRunResult(final_message, proposal, summary)


def main() -> None:
    print("Nenad Kajgana's AI Assistant — LangGraph Supervisor")
    try:
        while True:
            user_input = input("Ask anything about Nenad: \n").strip()
            if not user_input:
                continue
            print(f"\nAssistant: {run(user_input, chat_session_id='cli').message.content}\n")
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")


if __name__ == "__main__":
    main()
