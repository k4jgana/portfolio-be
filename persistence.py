import logging
import os
import re
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:///./chatbot.db"
DATABASE_URL = (os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL).strip()
FALLBACK_DATABASE_URL = (
    os.getenv("DATABASE_FALLBACK_URL", DEFAULT_DATABASE_URL).strip() or DEFAULT_DATABASE_URL
)


def _render_db_url(url: str) -> str:
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database url>"


def _connect_args(url: str) -> dict[str, bool]:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


def _new_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, connect_args=_connect_args(url))


def _initial_engine() -> tuple[Engine, str]:
    try:
        return _new_engine(DATABASE_URL), DATABASE_URL
    except Exception as exc:
        if DATABASE_URL == FALLBACK_DATABASE_URL:
            raise
        logger.warning(
            "Invalid DATABASE_URL=%s. Falling back to DATABASE_FALLBACK_URL=%s.",
            _render_db_url(DATABASE_URL),
            _render_db_url(FALLBACK_DATABASE_URL),
        )
        logger.warning("Original database error: %s", exc)
        return _new_engine(FALLBACK_DATABASE_URL), FALLBACK_DATABASE_URL


engine, ACTIVE_DATABASE_URL = _initial_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Visitor(Base):
    __tablename__ = "visitors"

    visitor_id = Column(String(128), primary_key=True, index=True)
    user_email = Column(String(320), nullable=True)
    firebase_uid = Column(String(256), nullable=True)
    first_seen = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_ip = Column(String(64), nullable=True)
    last_user_agent = Column(Text, nullable=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    chat_session_id = Column(String(128), primary_key=True, index=True)
    visitor_id = Column(String(128), ForeignKey("visitors.visitor_id"), nullable=False, index=True)
    user_email = Column(String(320), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_session_id = Column(String(128), ForeignKey("chat_sessions.chat_session_id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ChatEvent(Base):
    __tablename__ = "chat_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    visitor_id = Column(String(128), nullable=False, index=True)
    chat_session_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    query = Column(Text, nullable=True)
    response_chars = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    origin = Column(Text, nullable=True)
    user_email = Column(String(320), nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


def _switch_engine(url: str) -> None:
    global engine, ACTIVE_DATABASE_URL
    engine = _new_engine(url)
    SessionLocal.configure(bind=engine)
    ACTIVE_DATABASE_URL = url


def _switch_to_fallback(reason: str, exc: Exception | None = None) -> bool:
    if ACTIVE_DATABASE_URL == FALLBACK_DATABASE_URL:
        return False

    if exc is None:
        logger.warning(
            "Primary database unavailable (%s). Switching to fallback database %s.",
            reason,
            _render_db_url(FALLBACK_DATABASE_URL),
        )
    else:
        logger.warning(
            "Primary database unavailable (%s). Switching to fallback database %s.",
            reason,
            _render_db_url(FALLBACK_DATABASE_URL),
        )
        logger.warning("Original database error: %s", exc)

    _switch_engine(FALLBACK_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    return True


def init_db() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        if not _switch_to_fallback("startup", exc):
            raise


def get_db_session() -> Session:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        switched = _switch_to_fallback("session acquisition", exc)
        if not switched:
            raise
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def generate_identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class SessionOwnershipError(ValueError):
    """Raised when a chat session is used with a different visitor."""


def normalize_identifier(value: str | None, prefix: str) -> str:
    if value and value.strip():
        normalized = value.strip()
        if IDENTIFIER_PATTERN.fullmatch(normalized):
            return normalized
    return generate_identifier(prefix)


def get_recent_history(db: Session, chat_session_id: str, max_messages: int = 12) -> str:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_session_id == chat_session_id)
        .order_by(ChatMessage.id.desc())
        .limit(max_messages)
        .all()
    )
    ordered = list(reversed(rows))
    return "\n".join(f"{msg.role.upper()}: {msg.content}" for msg in ordered)


def upsert_visitor_and_session(
    db: Session,
    visitor_id: str,
    chat_session_id: str,
    user_email: str,
    firebase_uid: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    now = utcnow()
    session = db.query(ChatSession).filter(ChatSession.chat_session_id == chat_session_id).first()
    if session is not None and session.visitor_id != visitor_id:
        raise SessionOwnershipError("Chat session does not belong to this visitor.")

    visitor = db.query(Visitor).filter(Visitor.visitor_id == visitor_id).first()
    if visitor is None:
        visitor = Visitor(
            visitor_id=visitor_id,
            user_email=user_email,
            firebase_uid=firebase_uid,
            first_seen=now,
            last_seen=now,
            last_ip=ip_address,
            last_user_agent=user_agent,
        )
        db.add(visitor)
    else:
        if user_email and user_email != "guest":
            visitor.user_email = user_email
        elif not visitor.user_email:
            visitor.user_email = user_email
        if firebase_uid:
            visitor.firebase_uid = firebase_uid
        visitor.last_seen = now
        visitor.last_ip = ip_address
        visitor.last_user_agent = user_agent

    if session is None:
        session = ChatSession(
            chat_session_id=chat_session_id,
            visitor_id=visitor_id,
            user_email=user_email,
            started_at=now,
            last_seen=now,
        )
        db.add(session)
    else:
        if user_email and user_email != "guest":
            session.user_email = user_email
        elif not session.user_email:
            session.user_email = user_email
        session.last_seen = now

    db.commit()


def save_turn_pair(db: Session, chat_session_id: str, user_query: str, answer: str) -> None:
    db.add(ChatMessage(chat_session_id=chat_session_id, role="user", content=user_query))
    db.add(ChatMessage(chat_session_id=chat_session_id, role="ai", content=answer))
    db.commit()


def log_chat_event(
    db: Session,
    *,
    visitor_id: str,
    chat_session_id: str,
    event_type: str,
    status_code: int,
    query: str | None = None,
    response_chars: int | None = None,
    latency_ms: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    origin: str | None = None,
    user_email: str | None = None,
    error_detail: str | None = None,
) -> None:
    db.add(
        ChatEvent(
            visitor_id=visitor_id,
            chat_session_id=chat_session_id,
            event_type=event_type,
            query=query,
            response_chars=response_chars,
            status_code=status_code,
            latency_ms=latency_ms,
            ip_address=ip_address,
            user_agent=user_agent,
            origin=origin,
            user_email=user_email,
            error_detail=error_detail,
            created_at=utcnow(),
        )
    )
    db.commit()
