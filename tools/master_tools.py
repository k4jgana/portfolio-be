"""Admin write proposals and their deterministic, post-confirmation executor."""

import hashlib
import logging
from typing import Any, Literal

from langchain.tools import tool
from pydantic import ValidationError

from schemas import AdminActionProposal
from services.cd_service import add_cd, set_have
from utils.constants import get_vector_store

logger = logging.getLogger(__name__)


def _proposal_summary(proposal: AdminActionProposal) -> str:
    if proposal.action == "add_cd":
        return f"Add CD: {proposal.artist} — {proposal.album} (owned: {proposal.have})."
    if proposal.action == "update_cd_have_status":
        return f"Set CD ownership: {proposal.artist} — {proposal.album} → {proposal.have}."
    return f"Store knowledge record: {proposal.title}."


@tool
def propose_admin_change(
    action: Literal["add_cd", "update_cd_have_status", "upsert_record"],
    artist: str | None = None,
    album: str | None = None,
    have: bool | None = None,
    title: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    """Prepare one admin change for explicit approval; this tool never writes data.

    CD changes require artist, album, and ownership status. Knowledge storage
    requires a title and the exact neutral factual text. The returned proposal
    must be confirmed separately.
    """
    try:
        proposal = AdminActionProposal(
            action=action,
            artist=artist,
            album=album,
            have=have,
            title=title,
            text=text,
        )
    except ValidationError as exc:
        return {
            "status": "invalid",
            "message": "The requested change is missing required or valid values.",
            "errors": [error["loc"] for error in exc.errors()],
        }

    return {
        "status": "pending_confirmation",
        "proposal": proposal.model_dump(),
        "summary": _proposal_summary(proposal),
    }


def execute_admin_action(action: str, payload: dict[str, Any]) -> dict[str, str]:
    """Execute a previously validated and explicitly confirmed admin action."""
    try:
        proposal = AdminActionProposal(action=action, **payload)
    except ValidationError:
        logger.exception("Refusing invalid persisted admin action action=%s", action)
        return {"status": "error", "message": "The stored action was invalid and was not executed."}

    try:
        if proposal.action == "add_cd":
            result = add_cd(proposal.artist, proposal.album, proposal.have)
        elif proposal.action == "update_cd_have_status":
            result = set_have(proposal.artist, proposal.album, proposal.have)
        else:
            combined_text = f"{proposal.title} {proposal.text}"
            record_id = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()
            get_vector_store().add_texts(
                [combined_text],
                metadatas=[{"title": proposal.title, "text": proposal.text}],
                ids=[record_id],
            )
            result = {"status": "success", "message": f"Stored knowledge record '{proposal.title}'."}
    except Exception:
        logger.exception("Confirmed admin action failed action=%s", proposal.action)
        return {"status": "error", "message": "The confirmed change could not be completed."}

    return result
