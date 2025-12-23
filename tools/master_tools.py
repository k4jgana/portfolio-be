import logging
from langchain.tools import tool
from services.cd_service import get_cds, set_have, add_cd

logger = logging.getLogger(__name__)


@tool
def get_cd_collection() -> str:
    """
    Returns Nenad's CD collection from the database.

    Each entry includes:
    - Artist
    - Album
    - Whether he owns it (have=true/false)
    """
    logger.info("[MasterAgent][get_cd_collection] tool called")

    cds = get_cds()
    if not cds:
        return "No CDs found in the collection."
    return cds


@tool
def update_cd_have_status(artist: str, album: str, have: bool) -> str:
    """
    Updates whether Nenad owns a specific CD (have=true/false).

    Args:
        artist: Artist name
        album: Album title
        have: Boolean indicating ownership
    """
    logger.info(f"[MasterAgent][update_cd_have_status] tool called for {artist} - {album} -> {have}")

    set_have(artist, album, have)
    return f"Updated '{artist} - {album}' have status to {have}."


@tool
def add_new_cd(artist: str, album: str, have: bool = False) -> str:
    """
    Adds a new CD to Nenad's collection if it doesn't already exist.

    Args:
        artist: Artist name
        album: Album title
        have: Whether he owns it (default: True)
    """
    logger.info(f"[MasterAgent][add_new_cd] tool called for {artist} - {album} -> {have}")

    add_cd(artist, album, have)
    return f"Added CD: {artist} - {album} (have={have})"
