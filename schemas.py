from typing import Annotated, List, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, field_validator
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    context: str
    convo_history: str
    email: str
    next_step: Literal[
        "route",
        "knowledge",
        "main",
        "music",
        "movie",
        "master",
        "end",
    ]


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    history: str = Field(default="", max_length=8000)
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
    context: Optional[str] = None
    visitor_id: Optional[str] = None
    chat_session_id: Optional[str] = None
