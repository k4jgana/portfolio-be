import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from openai import AuthenticationError, RateLimitError
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from auth_verifier import verify_id_token
from persistence import (
    ChatEvent,
    ChatMessage,
    ChatSession,
    get_db_session,
    Visitor,
    get_recent_history,
    init_db,
    log_chat_event,
    utcnow,
    normalize_identifier,
    save_turn_pair,
    SessionOwnershipError,
    upsert_visitor_and_session,
)
from runner import run
from schemas import QueryResponse, QueryRequest
from utils.constants import MASTER_EMAIL

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -----------------------------
# FastAPI app
# -----------------------------
app = FastAPI(title="Nenad Kajgana AI Assistant")
trusted_hosts = [host.strip() for host in os.getenv("TRUSTED_HOSTS", "").split(",") if host.strip()]
if trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

def _env_int(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r. Using default %s.", name, raw_value, default)
        return default
    if parsed < minimum:
        logger.warning("%s must be >= %s. Using default %s.", name, minimum, default)
        return default
    return parsed


RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1)
RATE_LIMIT_REQUESTS = _env_int("RATE_LIMIT_REQUESTS", 30, minimum=1)
TRUST_X_FORWARDED_FOR = os.getenv("TRUST_X_FORWARDED_FOR", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}
_request_windows: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = threading.Lock()
_last_rate_cleanup = 0.0

# -----------------------------
# CORS Middleware
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # dev frontend
        "http://nenadkajgana.com",    # production HTTP (rare)
        "https://nenadkajgana.com",   # production HTTPS
    ],
    allow_methods=["*"],              # allow POST, GET, OPTIONS...
    allow_headers=["*"],              # allow Content-Type, Authorization...
    allow_credentials=True
)

# -----------------------------
# Startup hook
# -----------------------------
@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    db = _open_db_session()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Database readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Persistence service is temporarily unavailable.") from exc
    finally:
        db.close()
    return {"status": "ready"}


def _get_client_ip(request: Request) -> str:
    if TRUST_X_FORWARDED_FOR:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "").strip()
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    return token or None


def _allow_request(rate_limit_key: str) -> bool:
    global _last_rate_cleanup
    now = time.monotonic()
    with _rate_limit_lock:
        if now - _last_rate_cleanup >= RATE_LIMIT_WINDOW_SECONDS:
            for key, bucket in list(_request_windows.items()):
                while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
                    bucket.popleft()
                if not bucket:
                    del _request_windows[key]
            _last_rate_cleanup = now

        bucket = _request_windows[rate_limit_key]
        while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            return False
        bucket.append(now)
        return True


def _safe_log_chat_event(db: Session, **kwargs) -> None:
    try:
        log_chat_event(db, **kwargs)
    except Exception:
        db.rollback()
        logger.exception("Failed to log chat event.")


def _open_db_session() -> Session:
    try:
        return get_db_session()
    except Exception as exc:
        logger.exception("Failed to open database session: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Persistence service is temporarily unavailable.",
        ) from exc


def _provider_error_detail(exc: Exception) -> str | None:
    """Return a safe client-facing message for OpenAI auth/quota failures."""
    if isinstance(exc, AuthenticationError):
        return "The AI service is temporarily unavailable because its credentials are invalid."
    if isinstance(exc, RateLimitError):
        error_code = getattr(exc, "code", None)
        if error_code == "insufficient_quota" or "insufficient_quota" in str(exc):
            return "The AI service is temporarily unavailable because its usage quota is exhausted."
        return "The AI service is temporarily busy. Please try again shortly."
    return None


def _verify_admin_request(request: Request) -> str:
    master_email = (MASTER_EMAIL or "").strip().lower()
    if not master_email:
        raise HTTPException(status_code=503, detail="Analytics endpoint is not configured.")

    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        claims = verify_id_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc

    email = (claims.get("email") or "").strip().lower()
    email_verified = bool(claims.get("email_verified"))
    if not email or not email_verified or email != master_email:
        raise HTTPException(status_code=403, detail="Not authorized.")
    return email


# -----------------------------
# Explicit OPTIONS handler for /ask (preflight)
# -----------------------------
@app.options("/ask")
async def preflight(request: Request):
    """
    Handle CORS preflight requests explicitly.
    Required because Tailscale Funnel sometimes breaks automatic OPTIONS handling.
    """
    return Response(
        headers={
            "Access-Control-Allow-Origin": "https://nenadkajgana.com",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Visitor-Id, X-Chat-Session-Id",
        }
    )

# -----------------------------
# POST /ask endpoint
# -----------------------------
@app.post("/ask", response_model=QueryResponse)
async def ask(query_request: QueryRequest, request: Request):
    """
    Endpoint to send a user query to the agent.
    """
    started_at = time.monotonic()
    db = _open_db_session()
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    origin = request.headers.get("origin")
    requested_visitor_id = query_request.visitor_id or request.headers.get("x-visitor-id")
    requested_chat_session_id = query_request.chat_session_id or request.headers.get("x-chat-session-id")
    chat_session_id = normalize_identifier(requested_chat_session_id, prefix="session")
    visitor_id = (
        normalize_identifier(requested_visitor_id, prefix="visitor")
        if requested_visitor_id
        else None
    )
    if requested_chat_session_id and not visitor_id:
        existing_session = (
            db.query(ChatSession)
            .filter(ChatSession.chat_session_id == chat_session_id)
            .first()
        )
        if existing_session:
            visitor_id = existing_session.visitor_id
    if not visitor_id:
        visitor_id = normalize_identifier(None, prefix="visitor")
    user_email = "guest"
    firebase_uid = None

    try:
        token = _extract_bearer_token(request)
        if token:
            try:
                claims = verify_id_token(token)
            except ValueError as exc:
                latency_ms = int((time.monotonic() - started_at) * 1000)
                _safe_log_chat_event(
                    db,
                    visitor_id=visitor_id,
                    chat_session_id=chat_session_id,
                    event_type="auth_failed",
                    status_code=401,
                    query=query_request.query,
                    latency_ms=latency_ms,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    origin=origin,
                    user_email=user_email,
                    error_detail=str(exc),
                )
                raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc

            firebase_uid = claims.get("uid")
            token_email = (claims.get("email") or "").strip().lower()
            if token_email and claims.get("email_verified"):
                user_email = token_email

        rate_limit_key = f"{firebase_uid or 'anonymous'}:{ip_address}"
        if not _allow_request(rate_limit_key):
            latency_ms = int((time.monotonic() - started_at) * 1000)
            _safe_log_chat_event(
                db,
                visitor_id=visitor_id,
                chat_session_id=chat_session_id,
                event_type="rate_limited",
                status_code=429,
                query=query_request.query,
                latency_ms=latency_ms,
                ip_address=ip_address,
                user_agent=user_agent,
                origin=origin,
                user_email=user_email,
                error_detail="Too many requests.",
            )
            raise HTTPException(status_code=429, detail="Too many requests. Please retry shortly.")

        try:
            upsert_visitor_and_session(
                db,
                visitor_id=visitor_id,
                chat_session_id=chat_session_id,
                user_email=user_email,
                firebase_uid=firebase_uid,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except SessionOwnershipError as exc:
            db.rollback()
            latency_ms = int((time.monotonic() - started_at) * 1000)
            _safe_log_chat_event(
                db,
                visitor_id=visitor_id,
                chat_session_id=chat_session_id,
                event_type="session_mismatch",
                status_code=409,
                query=query_request.query,
                latency_ms=latency_ms,
                ip_address=ip_address,
                user_agent=user_agent,
                origin=origin,
                user_email=user_email,
                error_detail=str(exc),
            )
            raise HTTPException(
                status_code=409,
                detail="Session identifier does not match this visitor.",
            ) from exc

        persisted_history = get_recent_history(db, chat_session_id=chat_session_id, max_messages=12)
        history = persisted_history if persisted_history else query_request.history
        final_state = run(query_request.query, history, user_email)
        answer = final_state["messages"][-1].content if final_state["messages"] else ""
        save_turn_pair(db, chat_session_id=chat_session_id, user_query=query_request.query, answer=answer)

        latency_ms = int((time.monotonic() - started_at) * 1000)
        _safe_log_chat_event(
            db,
            visitor_id=visitor_id,
            chat_session_id=chat_session_id,
            event_type="chat_success",
            status_code=200,
            query=query_request.query,
            response_chars=len(answer),
            latency_ms=latency_ms,
            ip_address=ip_address,
            user_agent=user_agent,
            origin=origin,
            user_email=user_email,
        )
        return QueryResponse(answer=answer, visitor_id=visitor_id, chat_session_id=chat_session_id)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        provider_detail = _provider_error_detail(e)
        status_code = 503 if provider_detail else 500
        latency_ms = int((time.monotonic() - started_at) * 1000)
        _safe_log_chat_event(
            db,
            visitor_id=visitor_id,
            chat_session_id=chat_session_id,
            event_type="chat_error",
            status_code=status_code,
            query=query_request.query,
            latency_ms=latency_ms,
            ip_address=ip_address,
            user_agent=user_agent,
            origin=origin,
            user_email=user_email,
            error_detail=str(e),
        )
        logger.exception("Error processing query: %s", e)
        if provider_detail:
            raise HTTPException(status_code=503, detail=provider_detail) from e
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        db.close()


@app.get("/analytics/summary")
async def analytics_summary(request: Request):
    admin_email = _verify_admin_request(request)
    db = _open_db_session()
    try:
        now = utcnow()
        from_24h = now - timedelta(hours=24)
        total_visitors = db.query(func.count(Visitor.visitor_id)).scalar() or 0
        total_sessions = db.query(func.count(ChatSession.chat_session_id)).scalar() or 0
        total_messages = db.query(func.count(ChatMessage.id)).scalar() or 0
        total_events = db.query(func.count(ChatEvent.id)).scalar() or 0
        events_24h = (
            db.query(func.count(ChatEvent.id))
            .filter(ChatEvent.created_at >= from_24h)
            .scalar()
            or 0
        )
        anonymous_visitors = (
            db.query(func.count(Visitor.visitor_id))
            .filter((Visitor.user_email == "guest") | (Visitor.user_email.is_(None)))
            .scalar()
            or 0
        )
        authenticated_visitors = total_visitors - anonymous_visitors

        return {
            "admin": admin_email,
            "totals": {
                "visitors": total_visitors,
                "sessions": total_sessions,
                "messages": total_messages,
                "events": total_events,
            },
            "window_24h": {
                "events": events_24h,
            },
            "segments": {
                "anonymous_visitors": anonymous_visitors,
                "authenticated_visitors": authenticated_visitors,
            },
        }
    finally:
        db.close()
