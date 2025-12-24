import logging
from fastapi import FastAPI, HTTPException
from runner import run
from schemas import QueryResponse,QueryRequest
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Nenad Kajgana AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://nenadkajgana.com","https://nenadkajgana.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)




@app.post("/ask", response_model=QueryResponse)
async def ask(query_request: QueryRequest):
    """
    Endpoint to send a user query to the agent.
    """
    try:
        final_state = run(query_request.query, query_request.history, query_request.email)
        answer = final_state["messages"][-1].content if final_state["messages"] else ""

        return QueryResponse(answer=answer)

    except Exception as e:
        logger.exception("Error processing query: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
