import logging
import random
from typing import Annotated, Any, Literal

from langchain.tools import tool
from pydantic import Field

from utils.constants import get_letterboxd_service

logger = logging.getLogger(__name__)


@tool
def retrieve_movie_context(
    mode: Literal["recent", "genre", "personal_picks", "year"],
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
    genre: str | None = None,
    year: Annotated[int | None, Field(ge=1888, le=2100)] = None,
) -> dict[str, Any]:
    """Retrieve facts from Nenad's movie diary and ratings.

    Select recent, genre, personal_picks, or year. Genre mode requires genre;
    year mode requires year. This returns movie records for the final response.
    """
    logger.info("Retrieving movie context mode=%s limit=%s", mode, limit)
    if mode == "genre" and not (genre or "").strip():
        return {
            "status": "error",
            "mode": mode,
            "items": [],
            "message": "A genre is required to retrieve genre-based movie information.",
        }
    if mode == "year" and year is None:
        return {
            "status": "error",
            "mode": mode,
            "items": [],
            "message": "A year is required to retrieve year-based movie information.",
        }

    try:
        if mode == "recent":
            items = get_letterboxd_service().get_recent_ratings(limit=limit)[:limit]
        elif mode == "genre":
            items = get_letterboxd_service().get_ratings_by_genre(genre=genre.strip())
            random.shuffle(items)
            items = items[:limit]
        elif mode == "personal_picks":
            items = get_letterboxd_service().get_nenad_personal_picks()
            random.shuffle(items)
            items = items[:limit]
        else:
            items = get_letterboxd_service().get_ratings_by_year(year=year)[:limit]
    except Exception:
        logger.exception("Movie retrieval failed for mode=%s", mode)
        return {
            "status": "error",
            "mode": mode,
            "items": [],
            "message": "Nenad's movie information is temporarily unavailable.",
        }

    return {
        "status": "success" if items else "empty",
        "mode": mode,
        "items": [_normalize_movie(item) for item in items],
    }


def _normalize_movie(item: dict) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("title", "rating", "month", "description", "genre", "year")
        if key in item
    }
