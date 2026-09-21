"""Optional persistent LangGraph checkpoints for chat threads."""

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


def _checkpoint_url() -> str | None:
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url.startswith("postgresql"):
        return None
    return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)


@lru_cache(maxsize=1)
def get_checkpointer():
    """Return a process-wide Postgres checkpointer, or None when unavailable."""
    if os.getenv("LANGGRAPH_CHECKPOINTS_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        return None
    database_url = _checkpoint_url()
    if not database_url:
        return None

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(conninfo=database_url, kwargs={"autocommit": True}, open=True)
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
        return checkpointer
    except Exception:
        logger.exception("LangGraph checkpoints are unavailable; using persisted chat messages only.")
        return None


def close_checkpointer() -> None:
    """Release the connection pool during application shutdown."""
    checkpointer = get_checkpointer()
    pool = getattr(checkpointer, "conn", None)
    close = getattr(pool, "close", None)
    if close:
        close()
