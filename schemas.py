from typing import Annotated, List, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing import Optional

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    context: str
    convo_history:str
    next_step: Literal[
        "route",
        "knowledge",
        "main",
        "music"
    ]


class QueryRequest(BaseModel):
    query: str
    history: str = ""




class QueryResponse(BaseModel):
    answer: str
    context: Optional[str] = None

