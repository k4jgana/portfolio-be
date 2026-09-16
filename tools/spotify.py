import logging
import random
from typing import Annotated, Any, Literal

from langchain.tools import tool
from pydantic import Field

from services.cd_service import get_cd_records
from services.spotify_service import get_liked_songs
from services.lastfm_service import scrape_top_albums, scrape_top_artists

logger = logging.getLogger(__name__)


@tool
def retrieve_music_context(
    mode: Literal["recent_albums", "top_artists", "liked_songs", "cd_collection"],
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Retrieve facts about Nenad's music activity or CD collection.

    Select recent_albums for current album listening, top_artists for current
    artists, liked_songs for song suggestions, or cd_collection for owned and
    wanted physical albums. This returns data, not a written recommendation.
    """
    logger.info("Retrieving music context mode=%s limit=%s", mode, limit)
    try:
        if mode == "recent_albums":
            raw_items = scrape_top_albums()
            items = [
                {"album": item.get("album"), "artist": item.get("artist")}
                for item in raw_items[:limit]
            ]
        elif mode == "top_artists":
            items = [{"artist": artist} for artist in scrape_top_artists()[:limit]]
        elif mode == "liked_songs":
            raw_items = get_liked_songs(num_songs=300)
            random.shuffle(raw_items)
            items = [_normalize_song(item) for item in raw_items[:limit]]
            items = [item for item in items if item is not None]
        else:
            items = get_cd_records()[:limit]
    except Exception:
        logger.exception("Music retrieval failed for mode=%s", mode)
        return {
            "status": "error",
            "mode": mode,
            "items": [],
            "message": "Nenad's music information is temporarily unavailable.",
        }

    return {"status": "success" if items else "empty", "mode": mode, "items": items}


def _normalize_song(item: dict) -> dict[str, Any] | None:
    track = item.get("track") or {}
    name = track.get("name")
    if not name:
        return None
    artists = [
        artist.get("name")
        for artist in track.get("artists", [])
        if artist.get("name")
    ]
    album = track.get("album") or {}
    return {
        "song": name,
        "artists": artists,
        "album": album.get("name"),
        "added_at": item.get("added_at"),
    }
