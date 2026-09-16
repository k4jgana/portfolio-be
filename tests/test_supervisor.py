import asyncio
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from starlette.requests import Request

import app
from graphs import user_chat


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.bound_tool_names = []

    def bind_tools(self, tools):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


class SupervisorGraphTests(unittest.TestCase):
    def tearDown(self):
        user_chat.create_graph.cache_clear()

    def test_graphs_are_cached_with_distinct_allowlists(self):
        guest_model = ScriptedModel([])
        admin_model = ScriptedModel([])
        with patch.object(user_chat, "llm", guest_model):
            guest = user_chat.create_graph(False)
            self.assertIs(guest, user_chat.create_graph(False))
        user_chat.create_graph.cache_clear()
        with patch.object(user_chat, "llm", admin_model):
            user_chat.create_graph(True)

        self.assertEqual(
            guest_model.bound_tool_names,
            [
                "search_nenad_knowledge",
                "retrieve_music_context",
                "retrieve_movie_context",
            ],
        )
        self.assertEqual(
            admin_model.bound_tool_names,
            [
                "search_nenad_knowledge",
                "retrieve_music_context",
                "retrieve_movie_context",
                "add_new_cd",
                "update_cd_have_status",
                "upsert_record",
            ],
        )

    def test_direct_answer_ends_without_tool_execution(self):
        model = ScriptedModel([AIMessage(content="Hello!")])
        with patch.object(user_chat, "llm", model):
            graph = user_chat.create_graph(False)
            result = graph.invoke(
                {"messages": [HumanMessage(content="Say hello")], "convo_history": ""}
            )

        self.assertEqual(result["messages"][-1].content, "Hello!")
        self.assertEqual(len(model.calls), 1)
        self.assertFalse(
            any(isinstance(message, ToolMessage) for message in result["messages"])
        )

    def test_supervisor_executes_multiple_tools_then_writes_one_answer(self):
        tool_request = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "retrieve_music_context",
                    "args": {"mode": "recent_albums", "limit": 2},
                    "id": "music-1",
                    "type": "tool_call",
                },
                {
                    "name": "retrieve_movie_context",
                    "args": {"mode": "personal_picks", "limit": 2},
                    "id": "movie-1",
                    "type": "tool_call",
                },
            ],
        )
        model = ScriptedModel([tool_request, AIMessage(content="Combined answer")])
        with patch.object(user_chat, "llm", model), patch(
            "tools.spotify.scrape_top_albums",
            return_value=[{"album": "Album A", "artist": "Artist A"}],
        ), patch.object(
            user_chat.retrieve_movie_context.func.__globals__["lb"],
            "get_nenad_personal_picks",
            return_value=[{"title": "Movie A", "rating": 5.0}],
        ):
            graph = user_chat.create_graph(False)
            result = graph.invoke(
                {
                    "messages": [HumanMessage(content="Music and movie ideas?")],
                    "convo_history": "USER: Earlier question",
                }
            )

        tool_messages = [
            message
            for message in result["messages"]
            if isinstance(message, ToolMessage)
        ]
        self.assertEqual(len(tool_messages), 2)
        self.assertEqual(result["messages"][-1].content, "Combined answer")
        self.assertEqual(len(model.calls), 2)
        self.assertIn("Earlier question", model.calls[0][0].content)
        self.assertIn("Earlier question", model.calls[1][0].content)

    def test_supervisor_can_request_context_in_multiple_cycles(self):
        first_request = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "retrieve_music_context",
                    "args": {"mode": "top_artists", "limit": 1},
                    "id": "music-1",
                    "type": "tool_call",
                }
            ],
        )
        second_request = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "retrieve_movie_context",
                    "args": {"mode": "recent", "limit": 1},
                    "id": "movie-1",
                    "type": "tool_call",
                }
            ],
        )
        model = ScriptedModel(
            [first_request, second_request, AIMessage(content="Final answer")]
        )
        with patch.object(user_chat, "llm", model), patch(
            "tools.spotify.scrape_top_artists", return_value=["Artist A"]
        ), patch.object(
            user_chat.retrieve_movie_context.func.__globals__["lb"],
            "get_recent_ratings",
            return_value=[{"title": "Movie A", "rating": 4.5}],
        ):
            graph = user_chat.create_graph(False)
            result = graph.invoke(
                {"messages": [HumanMessage(content="Compare both")], "convo_history": ""}
            )

        self.assertEqual(len(model.calls), 3)
        self.assertEqual(
            len(
                [
                    message
                    for message in result["messages"]
                    if isinstance(message, ToolMessage)
                ]
            ),
            2,
        )
        self.assertEqual(result["messages"][-1].content, "Final answer")

    def test_retrieval_failure_returns_safe_structured_result(self):
        with patch(
            "tools.spotify.scrape_top_albums", side_effect=RuntimeError("secret detail")
        ):
            result = user_chat.retrieve_music_context.invoke(
                {"mode": "recent_albums", "limit": 3}
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["mode"], "recent_albums")
        self.assertEqual(result["items"], [])
        self.assertNotIn("secret detail", result["message"])


class AuthorizationTests(unittest.TestCase):
    def test_only_verified_exact_master_email_is_admin(self):
        with patch.object(app, "MASTER_EMAIL", "Owner@Example.com"):
            self.assertTrue(
                app._is_admin_claims(
                    {"email": " owner@example.com ", "email_verified": True}
                )
            )
            self.assertFalse(
                app._is_admin_claims(
                    {"email": "owner@example.com", "email_verified": False}
                )
            )
            self.assertFalse(
                app._is_admin_claims(
                    {"email": "someone@example.com", "email_verified": True}
                )
            )
            self.assertFalse(
                app._is_admin_claims(
                    {"email": "owner@example.com", "email_verified": "true"}
                )
            )

    def test_request_email_cannot_spoof_admin_access(self):
        is_admin = self._ask_and_capture_admin(
            claims=None,
            request_email="owner@example.com",
        )
        self.assertFalse(is_admin)

    def test_verified_master_claim_selects_admin_graph(self):
        is_admin = self._ask_and_capture_admin(
            claims={
                "uid": "firebase-user",
                "email": "OWNER@example.com",
                "email_verified": True,
            },
            request_email="guest",
        )
        self.assertTrue(is_admin)

    def _ask_and_capture_admin(self, *, claims, request_email):
        headers = []
        if claims is not None:
            headers.append((b"authorization", b"Bearer valid-token"))
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/ask",
                "headers": headers,
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 80),
                "scheme": "http",
                "query_string": b"",
            }
        )
        db = MagicMock()
        run_mock = MagicMock(return_value=AIMessage(content="Answer"))
        patches = [
            patch.object(app, "MASTER_EMAIL", "owner@example.com"),
            patch.object(app, "_open_db_session", return_value=db),
            patch.object(app, "create_question_submission", return_value="request-1"),
            patch.object(app, "_allow_request", return_value=True),
            patch.object(app, "upsert_visitor_and_session"),
            patch.object(app, "get_recent_history", return_value=""),
            patch.object(app, "save_turn_pair"),
            patch.object(app, "_safe_log_chat_event"),
            patch.object(app, "_safe_complete_question_submission"),
            patch.object(app, "run", run_mock),
        ]
        if claims is not None:
            patches.append(patch.object(app, "verify_id_token", return_value=claims))

        for active_patch in patches:
            active_patch.start()
        try:
            response = asyncio.run(
                app.ask(
                    app.QueryRequest(
                        query="Hello",
                        email=request_email,
                    ),
                    request,
                )
            )
        finally:
            for active_patch in reversed(patches):
                active_patch.stop()

        self.assertEqual(response.answer, "Answer")
        return run_mock.call_args.kwargs["is_admin"]


if __name__ == "__main__":
    unittest.main()
