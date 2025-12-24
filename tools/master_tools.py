import logging
from langchain.tools import tool
from services.cd_service import get_cds, set_have, add_cd
from utils.constants import vector_store

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

@tool
def upsert_record(title: str, text: str) -> str:
    """
    Embeds a single text record and upserts it into Pinecone via LangChain's PineconeVectorStore.

    Args:
        title: Title or name of the record.
        text: Content to be embedded and stored.
    """
    logger.info(f"[MasterAgent][upsert_record] Upserting record: {title}")

    try:
        combined_text = f"{title} {text}"
        metadata = {"title": title, "text": text}
        vector_store.add_texts([combined_text], metadatas=[metadata])

        logger.info(f"[MasterAgent][upsert_record] Successfully upserted '{title}' into Pinecone.")
        return f"✅ Successfully embedded and upserted '{title}' into Pinecone."
    except Exception as e:
        logger.error(f"[MasterAgent][upsert_record] Failed to upsert record: {e}", exc_info=True)
        return f"❌ Failed to upsert '{title}' into Pinecone: {e}"
