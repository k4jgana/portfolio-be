# AGENTS.md — portfolio-be AI Assistant

## What is this?

A FastAPI backend (Python 3.10+) for answering questions about movies and music that uses:
- LangChain + LangGraph for agent orchestration
- Pinecone (vector DB) for storing embeddings (OpenAI)
- Spotify and Letterboxd APIs/tools for personalized recommendations

## How does it work?

- `/ask` selects one of two cached LangGraph workflows: guest/read-only or verified-admin.
- The explicit graph loops between a supervisor and `ToolNode` until the supervisor returns a final answer.
- Three typed façade tools return structured knowledge, music, movie, and CD facts without writing prose.
- Only the supervisor writes chat responses; the admin graph can create protected change proposals, while a separate authenticated confirmation endpoint performs the mutation.
- All settings/API keys live in a .env file (see README)

## Change discipline

- For every major behavioral, architectural, deployment, API, or configuration change, update `README.md` in the same change so it remains an accurate operating guide.
- For every major change, run the relevant automated tests before handoff. Report the command and result; add or update tests when behavior changes.

## Main components

- app.py: FastAPI app with /ask endpoint
- runner.py: Selects a compiled graph and returns its final assistant message
- agents/supervisor_agent.py: Supervisor model invocation
- graphs/user_chat.py: StateGraph and fixed guest/admin allowlists
- services/: Integrations for 3rd-party APIs
- utils/: constants and prompt loader helpers
- prompts/: agent prompt templates

## Deploying

1. Copy your .env file as needed.
2. `docker compose up --build`
3. Visit http://localhost:8000/docs for Swagger API docs.

Optimize further by tweaking Gunicorn/worker count or Python base image.
