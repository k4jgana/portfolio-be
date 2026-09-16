"""Build and send monthly visitor-question reports.

Usage:
    python -m monthly_report preview 2026-09
    python -m monthly_report send-test
    python -m monthly_report send-due
"""

from __future__ import annotations

import argparse
import base64
import csv
import fcntl
import hashlib
import html
import io
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from persistence import (
    Base,
    ChatEvent,
    DATABASE_URL,
    FALLBACK_DATABASE_URL,
    MonthlyReportAttempt,
    MonthlyReportDelivery,
    QuestionSubmission,
    utcnow,
)

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
EMAIL_BODY_QUESTION_LIMIT = 100
# Resend accepts 40 MB after base64 encoding. This leaves ample room for the
# message body and encoding overhead.
MAX_CSV_BYTES_PER_EMAIL = 24 * 1024 * 1024
LOCK_PATH = Path(os.getenv("MONTHLY_REPORT_LOCK_PATH", "/app/data/monthly-report.lock"))


@dataclass(frozen=True)
class QuestionRecord:
    record_id: str
    visitor_id: str
    chat_session_id: str
    question: str
    outcome: str
    status_code: int | None
    submitted_at: datetime
    legacy: bool = False


@dataclass(frozen=True)
class EmailPart:
    part_number: int
    total_parts: int
    subject: str
    text_body: str
    html_body: str
    csv_base64: str
    payload_hash: str


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env_value(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _email_config() -> tuple[str, str, str]:
    recipient = _env_value("MONTHLY_REPORT_TO") or ""
    sender = _env_value("MONTHLY_REPORT_FROM") or ""
    api_key = _env_value("RESEND_API_KEY") or ""
    if not recipient or not sender or not api_key:
        raise RuntimeError(
            "RESEND_API_KEY, MONTHLY_REPORT_TO, and MONTHLY_REPORT_FROM must be configured."
        )
    return recipient, sender, api_key


def _parse_month(value: str) -> tuple[int, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError(f"Invalid month {value!r}; expected YYYY-MM.") from exc
    return parsed.year, parsed.month


def _month_string(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    year, month_number = _parse_month(month)
    next_year, next_month = _next_month(year, month_number)
    return (
        datetime(year, month_number, 1, tzinfo=timezone.utc),
        datetime(next_year, next_month, 1, tzinfo=timezone.utc),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sqlite_file_exists(url: str) -> bool:
    parsed = make_url(url)
    if parsed.drivername != "sqlite" or parsed.database in {None, "", ":memory:"}:
        return True
    return Path(parsed.database).exists()


def _source_engines() -> list[tuple[str, Engine]]:
    sources: list[tuple[str, Engine]] = []
    seen: set[str] = set()
    for label, url in (("primary", DATABASE_URL), ("fallback", FALLBACK_DATABASE_URL)):
        normalized = str(make_url(url))
        if normalized in seen:
            continue
        seen.add(normalized)
        if label == "fallback" and not _sqlite_file_exists(url):
            logger.info("Fallback database does not exist; skipping it.")
            continue
        sources.append((label, create_engine(url, pool_pre_ping=True)))
    return sources


def _read_source(label: str, engine: Engine, start: datetime, end: datetime) -> list[QuestionRecord]:
    table_names = set(inspect(engine).get_table_names())
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    records: list[QuestionRecord] = []
    try:
        first_submission: datetime | None = None
        if QuestionSubmission.__tablename__ in table_names:
            earliest = (
                db.query(QuestionSubmission.submitted_at)
                .order_by(QuestionSubmission.submitted_at.asc())
                .first()
            )
            first_submission = _as_utc(earliest[0]) if earliest else None
            rows = (
                db.query(QuestionSubmission)
                .filter(
                    QuestionSubmission.submitted_at >= start,
                    QuestionSubmission.submitted_at < end,
                )
                .order_by(QuestionSubmission.submitted_at.asc())
                .all()
            )
            records.extend(
                QuestionRecord(
                    record_id=row.request_id,
                    visitor_id=row.visitor_id,
                    chat_session_id=row.chat_session_id,
                    question=row.question,
                    outcome=row.outcome,
                    status_code=row.status_code,
                    submitted_at=_as_utc(row.submitted_at),
                )
                for row in rows
            )

        # Chat events predate reliable submission capture. Once the first new
        # submission exists, events at or after that instant are duplicates.
        if ChatEvent.__tablename__ in table_names:
            query = db.query(ChatEvent).filter(
                ChatEvent.query.isnot(None),
                ChatEvent.created_at >= start,
                ChatEvent.created_at < end,
            )
            if first_submission is not None:
                query = query.filter(ChatEvent.created_at < first_submission)
            for row in query.order_by(ChatEvent.created_at.asc()).all():
                submitted_at = _as_utc(row.created_at)
                legacy_key = "|".join(
                    (
                        row.visitor_id,
                        row.chat_session_id,
                        submitted_at.isoformat(),
                        row.query or "",
                        row.event_type,
                    )
                )
                records.append(
                    QuestionRecord(
                        record_id="legacy-" + hashlib.sha256(legacy_key.encode()).hexdigest(),
                        visitor_id=row.visitor_id,
                        chat_session_id=row.chat_session_id,
                        question=row.query or "",
                        outcome=f"legacy:{row.event_type}",
                        status_code=row.status_code,
                        submitted_at=submitted_at,
                        legacy=True,
                    )
                )
    finally:
        db.close()
    logger.info("Read %d question records from %s database.", len(records), label)
    return records


def load_questions(month: str) -> list[QuestionRecord]:
    start, end = _month_bounds(month)
    by_id: dict[str, QuestionRecord] = {}
    sources = _source_engines()
    if not sources:
        raise RuntimeError("No configured database source is available.")
    for label, engine in sources:
        try:
            for record in _read_source(label, engine, start, end):
                by_id.setdefault(record.record_id, record)
        except Exception as exc:
            raise RuntimeError(f"Could not read the {label} database; report delivery postponed.") from exc
        finally:
            engine.dispose()
    return sorted(by_id.values(), key=lambda item: (item.submitted_at, item.record_id))


def _csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _csv_bytes(records: list[QuestionRecord]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("timestamp_utc", "visitor_id", "chat_session_id", "outcome", "status_code", "question"))
    for record in records:
        writer.writerow(
            tuple(
                _csv_safe(value)
                for value in (
                    record.submitted_at.isoformat(),
                    record.visitor_id,
                    record.chat_session_id,
                    record.outcome,
                    record.status_code,
                    record.question,
                )
            )
        )
    return output.getvalue().encode("utf-8-sig")


def _split_for_attachments(records: list[QuestionRecord]) -> list[list[QuestionRecord]]:
    chunks: list[list[QuestionRecord]] = []
    current: list[QuestionRecord] = []
    for record in records:
        candidate = current + [record]
        if current and len(_csv_bytes(candidate)) > MAX_CSV_BYTES_PER_EMAIL:
            chunks.append(current)
            current = [record]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _render_bodies(month: str, records: list[QuestionRecord]) -> tuple[str, str]:
    visitors = len({record.visitor_id for record in records})
    legacy_count = sum(record.legacy for record in records)
    shown = records[:EMAIL_BODY_QUESTION_LIMIT]
    text_lines = [
        f"Monthly visitor-question report for {month}",
        f"Visitors: {visitors}",
        f"Questions: {len(records)}",
    ]
    if legacy_count:
        text_lines.append(f"Legacy records: {legacy_count} (coverage may be incomplete)")
    text_lines.append("")

    html_parts = [
        f"<h1>Monthly visitor-question report for {html.escape(month)}</h1>",
        f"<p><strong>Visitors:</strong> {visitors}<br><strong>Questions:</strong> {len(records)}</p>",
    ]
    if legacy_count:
        html_parts.append(
            f"<p><strong>Legacy records:</strong> {legacy_count} (coverage may be incomplete)</p>"
        )

    grouped: dict[str, dict[str, list[QuestionRecord]]] = {}
    for record in shown:
        grouped.setdefault(record.visitor_id, {}).setdefault(record.chat_session_id, []).append(record)
    for visitor_id, sessions in grouped.items():
        text_lines.extend(("", f"Visitor: {visitor_id}"))
        html_parts.append(f"<h2>Visitor: {html.escape(visitor_id)}</h2>")
        for session_id, session_records in sessions.items():
            text_lines.append(f"  Session: {session_id}")
            html_parts.append(f"<h3>Session: {html.escape(session_id)}</h3><ol>")
            for record in session_records:
                timestamp = record.submitted_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                status = record.outcome + (f" / HTTP {record.status_code}" if record.status_code else "")
                text_lines.append(f"    [{timestamp}] [{status}] {record.question}")
                html_parts.append(
                    "<li>"
                    f"<time>{html.escape(timestamp)}</time> "
                    f"<strong>[{html.escape(status)}]</strong> "
                    f"{html.escape(record.question)}"
                    "</li>"
                )
            html_parts.append("</ol>")
    if len(records) > len(shown):
        remainder = len(records) - len(shown)
        text_lines.extend(("", f"{remainder} additional questions are included in the CSV attachment."))
        html_parts.append(f"<p>{remainder} additional questions are included in the CSV attachment.</p>")
    return "\n".join(text_lines), "".join(html_parts)


def build_email_parts(month: str, records: list[QuestionRecord]) -> list[EmailPart]:
    if not records:
        return []
    text_body, html_body = _render_bodies(month, records)
    chunks = _split_for_attachments(records)
    total_parts = len(chunks)
    parts: list[EmailPart] = []
    for index, chunk in enumerate(chunks, start=1):
        suffix = f" (part {index}/{total_parts})" if total_parts > 1 else ""
        subject = f"Portfolio questions — {month}{suffix}"
        csv_base64 = base64.b64encode(_csv_bytes(chunk)).decode("ascii")
        payload_hash = hashlib.sha256(
            json.dumps(
                {
                    "subject": subject,
                    "text": text_body,
                    "html": html_body,
                    "csv": csv_base64,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        parts.append(
            EmailPart(
                part_number=index,
                total_parts=total_parts,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                csv_base64=csv_base64,
                payload_hash=payload_hash,
            )
        )
    return parts


def _primary_session() -> tuple[Engine, Session]:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)()


def _save_empty_marker(db: Session, month: str, recipient: str) -> None:
    existing = (
        db.query(MonthlyReportDelivery)
        .filter_by(report_month=month, recipient=recipient, part_number=0)
        .first()
    )
    if existing is None:
        db.add(
            MonthlyReportDelivery(
                report_month=month,
                recipient=recipient,
                part_number=0,
                total_parts=0,
                status="skipped_empty",
                subject="",
                text_body="",
                html_body="",
                payload_hash=hashlib.sha256(f"empty:{month}".encode()).hexdigest(),
            )
        )
        db.commit()


def _get_or_create_delivery(
    db: Session, month: str, recipient: str, part: EmailPart
) -> MonthlyReportDelivery:
    delivery = (
        db.query(MonthlyReportDelivery)
        .filter_by(report_month=month, recipient=recipient, part_number=part.part_number)
        .first()
    )
    if delivery is not None:
        return delivery
    delivery = MonthlyReportDelivery(
        report_month=month,
        recipient=recipient,
        part_number=part.part_number,
        total_parts=part.total_parts,
        status="prepared",
        subject=part.subject,
        text_body=part.text_body,
        html_body=part.html_body,
        csv_base64=part.csv_base64,
        payload_hash=part.payload_hash,
    )
    db.add(delivery)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return (
            db.query(MonthlyReportDelivery)
            .filter_by(report_month=month, recipient=recipient, part_number=part.part_number)
            .one()
        )
    db.refresh(delivery)
    return delivery


def _record_attempt(
    db: Session,
    delivery: MonthlyReportDelivery,
    *,
    outcome: str,
    http_status: int | None = None,
    provider_message_id: str | None = None,
    detail: str | None = None,
) -> None:
    delivery.status = outcome
    delivery.provider_message_id = provider_message_id or delivery.provider_message_id
    delivery.updated_at = utcnow()
    db.add(
        MonthlyReportAttempt(
            delivery_id=delivery.id,
            outcome=outcome,
            http_status=http_status,
            provider_message_id=provider_message_id,
            detail=(detail or "")[:2000] or None,
        )
    )
    db.commit()


def _send_delivery(
    db: Session,
    delivery: MonthlyReportDelivery,
    *,
    api_key: str,
    sender: str,
) -> None:
    if delivery.status in {"sent", "delivery_unknown"}:
        return
    recipient_hash = hashlib.sha256(delivery.recipient.encode()).hexdigest()[:16]
    idempotency_key = (
        f"monthly-questions/{delivery.report_month}/{recipient_hash}/{delivery.part_number}"
    )
    payload = {
        "from": sender,
        "to": [delivery.recipient],
        "subject": delivery.subject,
        "text": delivery.text_body,
        "html": delivery.html_body,
        "attachments": [
            {
                "filename": f"portfolio-questions-{delivery.report_month}-part-{delivery.part_number}.csv",
                "content": delivery.csv_base64,
            }
        ],
    }
    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            json=payload,
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        _record_attempt(db, delivery, outcome="delivery_unknown", detail=str(exc))
        raise RuntimeError(
            "Resend delivery result is unknown; inspect the Resend dashboard before retrying."
        ) from exc

    try:
        response_data = response.json()
    except ValueError:
        response_data = {}
    if not response.is_success:
        detail = response_data.get("message") or response.text or "Resend rejected the request."
        _record_attempt(
            db,
            delivery,
            outcome="failed",
            http_status=response.status_code,
            detail=detail,
        )
        raise RuntimeError(f"Resend rejected report delivery with HTTP {response.status_code}: {detail}")

    provider_id = response_data.get("id")
    if not provider_id:
        _record_attempt(
            db,
            delivery,
            outcome="delivery_unknown",
            http_status=response.status_code,
            detail="Successful Resend response did not contain a message ID.",
        )
        raise RuntimeError("Resend accepted the request without returning a message ID.")
    _record_attempt(
        db,
        delivery,
        outcome="sent",
        http_status=response.status_code,
        provider_message_id=provider_id,
    )


def send_month(month: str) -> str:
    _parse_month(month)
    recipient, sender, api_key = _email_config()

    records = load_questions(month)
    engine, db = _primary_session()
    try:
        if not records:
            _save_empty_marker(db, month, recipient)
            logger.info("No questions were recorded for %s; no email sent.", month)
            return "skipped_empty"
        for part in build_email_parts(month, records):
            delivery = _get_or_create_delivery(db, month, recipient, part)
            _send_delivery(db, delivery, api_key=api_key, sender=sender)
        return "sent"
    finally:
        db.close()
        engine.dispose()


def _due_months(now: datetime) -> list[str]:
    start_value = _env_value("MONTHLY_REPORT_START_MONTH") or ""
    if not start_value:
        raise RuntimeError("MONTHLY_REPORT_START_MONTH must be configured as YYYY-MM.")
    start_year, start_month = _parse_month(start_value)
    current_month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now < current_month_start.replace(hour=9):
        current_year, current_number = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    else:
        current_year, current_number = now.year, now.month
    # Reports always cover a completed month, so stop before the current month.
    stop_year, stop_month = now.year, now.month
    if now < current_month_start.replace(hour=9):
        stop_year, stop_month = current_year, current_number

    result: list[str] = []
    year, month = start_year, start_month
    while (year, month) < (stop_year, stop_month):
        result.append(_month_string(year, month))
        year, month = _next_month(year, month)
    return result


def send_due(now: datetime | None = None) -> int:
    if not _bool_env("MONTHLY_REPORT_ENABLED"):
        logger.info("Monthly reporting is disabled.")
        return 0
    now = _as_utc(now or utcnow())
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.info("Another monthly report process is already running.")
            return 0
        failures = 0
        for month in _due_months(now):
            try:
                result = send_month(month)
                logger.info("Monthly report %s: %s.", month, result)
            except Exception:
                failures += 1
                logger.exception("Monthly report %s failed.", month)
        return 1 if failures else 0


def send_test() -> None:
    recipient, sender, api_key = _email_config()
    response = httpx.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": [recipient],
            "subject": "Portfolio monthly report test",
            "text": "Your Portfolio monthly visitor-question reports are configured correctly.",
            "html": "<p>Your Portfolio monthly visitor-question reports are configured correctly.</p>",
        },
        timeout=30.0,
    )
    if not response.is_success:
        try:
            detail = response.json().get("message")
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Resend rejected the test email with HTTP {response.status_code}: {detail}")
    logger.info("Test email accepted by Resend: %s", response.json().get("id", "unknown ID"))


def preview(month: str) -> None:
    records = load_questions(month)
    if not records:
        print(f"No questions recorded for {month}. No email would be sent.")
        return
    text_body, _ = _render_bodies(month, records)
    print(text_body)
    print(f"\nCSV rows: {len(records)}")
    print(f"Email parts: {len(_split_for_attachments(records))}")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preview_parser = subparsers.add_parser("preview", help="Preview a month without writes or email.")
    preview_parser.add_argument("month", help="Month in YYYY-MM format.")
    subparsers.add_parser("send-test", help="Send one synthetic configuration test.")
    subparsers.add_parser("send-due", help="Send all enabled, due monthly reports.")
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            preview(args.month)
            return 0
        if args.command == "send-test":
            send_test()
            return 0
        return send_due()
    except Exception as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
