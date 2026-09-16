import base64
import csv
import io
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import monthly_report
from monthly_report import (
    QuestionRecord,
    _email_config,
    _read_source,
    _csv_bytes,
    _due_months,
    _month_bounds,
    build_email_parts,
)
from persistence import (
    Base,
    ChatEvent,
    MonthlyReportDelivery,
    QuestionSubmission,
    complete_question_submission,
    create_question_submission,
)


def question(**overrides):
    values = {
        "record_id": "request-1",
        "visitor_id": "visitor-1",
        "chat_session_id": "session-1",
        "question": "What is Nenad building?",
        "outcome": "success",
        "status_code": 200,
        "submitted_at": datetime(2026, 9, 10, 12, 30, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return QuestionRecord(**values)


class MonthlyReportTests(unittest.TestCase):
    def test_month_bounds_handle_year_boundary(self):
        start, end = _month_bounds("2026-12")
        self.assertEqual(start, datetime(2026, 12, 1, tzinfo=timezone.utc))
        self.assertEqual(end, datetime(2027, 1, 1, tzinfo=timezone.utc))

    def test_empty_report_has_no_email_parts(self):
        self.assertEqual(build_email_parts("2026-09", []), [])

    def test_report_groups_questions_and_attaches_all_rows(self):
        records = [
            question(),
            question(
                record_id="request-2",
                chat_session_id="session-2",
                question="Recommend an album",
            ),
        ]
        parts = build_email_parts("2026-09", records)
        self.assertEqual(len(parts), 1)
        self.assertIn("Visitor: visitor-1", parts[0].text_body)
        decoded = base64.b64decode(parts[0].csv_base64).decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(decoded)))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2][-1], "Recommend an album")

    def test_each_visitor_heading_appears_once(self):
        records = [
            question(record_id="1", visitor_id="visitor-a"),
            question(record_id="2", visitor_id="visitor-b", chat_session_id="session-b"),
            question(record_id="3", visitor_id="visitor-a", chat_session_id="session-2"),
        ]
        part = build_email_parts("2026-09", records)[0]
        self.assertEqual(part.text_body.count("Visitor: visitor-a"), 1)
        self.assertIn("Session: session-1", part.text_body)
        self.assertIn("Session: session-2", part.text_body)

    def test_csv_neutralizes_spreadsheet_formulas(self):
        data = _csv_bytes([question(question="=HYPERLINK(\"bad\")")])
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
        self.assertEqual(rows[1][-1], "'=HYPERLINK(\"bad\")")

    def test_previous_month_is_due_only_after_0900_on_first(self):
        with patch.dict(os.environ, {"MONTHLY_REPORT_START_MONTH": "2026-09"}):
            before = datetime(2026, 10, 1, 8, 59, tzinfo=timezone.utc)
            after = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
            self.assertEqual(_due_months(before), [])
            self.assertEqual(_due_months(after), ["2026-09"])

    def test_quoted_docker_env_sender_is_normalized(self):
        with patch.dict(
            os.environ,
            {
                "RESEND_API_KEY": "re_test",
                "MONTHLY_REPORT_TO": "owner@example.com",
                "MONTHLY_REPORT_FROM": '"Portfolio Reports <questions@reports.example.com>"',
            },
        ):
            recipient, sender, api_key = _email_config()
            self.assertEqual(recipient, "owner@example.com")
            self.assertEqual(sender, "Portfolio Reports <questions@reports.example.com>")
            self.assertEqual(api_key, "re_test")

    def test_missed_months_are_caught_up(self):
        with patch.dict(os.environ, {"MONTHLY_REPORT_START_MONTH": "2026-09"}):
            now = datetime(2026, 12, 4, 12, 0, tzinfo=timezone.utc)
            self.assertEqual(_due_months(now), ["2026-09", "2026-10", "2026-11"])

    def test_submission_lifecycle_is_persisted(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            request_id = create_question_submission(
                db,
                visitor_id="visitor-1",
                chat_session_id="session-1",
                question="Will this be recorded?",
            )
            complete_question_submission(
                db,
                request_id=request_id,
                outcome="success",
                status_code=200,
            )
            row = db.query(QuestionSubmission).filter_by(request_id=request_id).one()
            self.assertEqual(row.outcome, "success")
            self.assertEqual(row.status_code, 200)
            self.assertIsNotNone(row.completed_at)
        finally:
            db.close()
            engine.dispose()

    def test_legacy_events_are_included_only_before_new_capture(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            db.add(
                ChatEvent(
                    visitor_id="legacy-visitor",
                    chat_session_id="legacy-session",
                    event_type="chat_success",
                    query="Old question",
                    status_code=200,
                    created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                )
            )
            db.add(
                QuestionSubmission(
                    request_id="new-request",
                    visitor_id="new-visitor",
                    chat_session_id="new-session",
                    question="New question",
                    outcome="success",
                    status_code=200,
                    submitted_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
                )
            )
            db.add(
                ChatEvent(
                    visitor_id="new-visitor",
                    chat_session_id="new-session",
                    event_type="chat_success",
                    query="New question",
                    status_code=200,
                    created_at=datetime(2026, 9, 2, 0, 0, 1, tzinfo=timezone.utc),
                )
            )
            db.commit()
            records = _read_source(
                "test",
                engine,
                datetime(2026, 9, 1, tzinfo=timezone.utc),
                datetime(2026, 10, 1, tzinfo=timezone.utc),
            )
            self.assertEqual([record.question for record in records], ["New question", "Old question"])
            self.assertEqual(sum(record.legacy for record in records), 1)
        finally:
            db.close()
            engine.dispose()

    def test_empty_month_records_skip_without_calling_resend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = create_engine(f"sqlite:///{temp_dir}/report.db")
            Base.metadata.create_all(engine)
            db = sessionmaker(bind=engine)()
            with patch.dict(
                os.environ,
                {
                    "RESEND_API_KEY": "test-key",
                    "MONTHLY_REPORT_TO": "owner@example.com",
                    "MONTHLY_REPORT_FROM": "Reports <reports@example.com>",
                },
            ), patch.object(monthly_report, "load_questions", return_value=[]), patch.object(
                monthly_report, "_primary_session", return_value=(engine, db)
            ), patch.object(monthly_report.httpx, "post") as post:
                result = monthly_report.send_month("2026-09")
                self.assertEqual(result, "skipped_empty")
                post.assert_not_called()
                check_engine = create_engine(f"sqlite:///{temp_dir}/report.db")
                check_db = sessionmaker(bind=check_engine)()
                try:
                    marker = check_db.query(MonthlyReportDelivery).one()
                    self.assertEqual(marker.status, "skipped_empty")
                finally:
                    check_db.close()
                    check_engine.dispose()


if __name__ == "__main__":
    unittest.main()
