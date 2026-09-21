from typing import Annotated, Any, List, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, field_validator
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    email: str = Field(default="guest", max_length=320)
    visitor_id: Optional[str] = Field(default=None, max_length=128)
    chat_session_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Query must not be empty.")
        return trimmed

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        trimmed = value.strip()
        return trimmed if trimmed else "guest"


class QueryResponse(BaseModel):
    answer: str
    visitor_id: Optional[str] = None
    chat_session_id: Optional[str] = None
    pending_action: Optional["PendingActionResponse"] = None


class PendingActionResponse(BaseModel):
    action_id: str
    action: Literal["add_cd", "update_cd_have_status", "upsert_record"]
    summary: str


class AdminActionProposal(BaseModel):
    """Validated, non-executing request awaiting a separate admin confirmation."""

    action: Literal["add_cd", "update_cd_have_status", "upsert_record"]
    artist: Optional[str] = Field(default=None, min_length=1, max_length=300)
    album: Optional[str] = Field(default=None, min_length=1, max_length=300)
    have: Optional[bool] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    text: Optional[str] = Field(default=None, min_length=1, max_length=4000)

    @field_validator("artist", "album", "title", "text")
    @classmethod
    def trim_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Must not be empty.")
        return trimmed

    def model_post_init(self, __context: Any) -> None:
        if self.action in {"add_cd", "update_cd_have_status"}:
            if not self.artist or not self.album or self.have is None:
                raise ValueError("CD changes require artist, album, and ownership status.")
        elif not self.title or not self.text:
            raise ValueError("Knowledge upserts require title and exact factual text.")


class CDCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    artist: str = Field(..., min_length=1, max_length=300)
    have: bool = False

    @field_validator("name", "artist")
    @classmethod
    def trim_cd_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Must not be empty.")
        return trimmed


class CDUpdate(CDCreate):
    pass


class CDResponse(CDCreate):
    id: int

    model_config = {"from_attributes": True}
