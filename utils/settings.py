"""Validated, environment-backed configuration for runtime dependencies."""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


def _int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        return default
    return value if value >= minimum else default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    master_email: str | None
    openai_api_key: str | None
    pinecone_api_key: str | None
    pinecone_index: str
    namespace: str
    spotify_client_id: str | None
    spotify_client_secret: str | None
    spotify_redirect_uri: str | None
    spotify_refresh_token: str | None
    model_name: str
    model_temperature: float
    model_timeout_seconds: int
    model_max_retries: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        master_email=os.getenv("MASTER_EMAIL"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        pinecone_api_key=os.getenv("PINECONE_API_KEY"),
        pinecone_index=os.getenv("PINECONE_INDEX", "nenad-info"),
        namespace=os.getenv("NAMESPACE", "default"),
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        spotify_refresh_token=os.getenv("SPOTIFY_REFRESH_TOKEN"),
        model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        model_temperature=_float("OPENAI_TEMPERATURE", 0.2),
        model_timeout_seconds=_int("OPENAI_TIMEOUT_SECONDS", 45, minimum=1),
        model_max_retries=_int("OPENAI_MAX_RETRIES", 2, minimum=0),
    )
