from typing import Annotated, List, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    context: str
    convo_history:str
    email:str
    next_step: Literal[
        "route",
        "knowledge",
        "main",
        "music",
        "master"
    ]


class QueryRequest(BaseModel):
    query: str
    history: str = ""
    email:str




class QueryResponse(BaseModel):
    answer: str
    context: Optional[str] = None

class CD(Base):
    __tablename__ = "cd-inventory"
    id = Column(Integer, primary_key=True)
    artist = Column(String, nullable=False)
    album = Column(String, nullable=False)
    have = Column(Boolean, default=False)

