# AGENTS.md — portfolio-be AI Assistant

## What is this?

A FastAPI backend (Python 3.10+) for answering questions about movies and music that uses:
- LangChain + LangGraph for agent orchestration
- Pinecone (vector DB) for storing embeddings (OpenAI)
- Spotify and Letterboxd APIs/tools for personalized recommendations

## How does it work?

- `/ask` endpoint takes a query and history, routes to the right agent (music, movie, knowledge, etc) via a router agent
- Responses are retrieved using Pinecone vectors (personal knowledge) + live lookups from Spotify and Letterboxd as needed
- All settings/API keys live in a .env file (see README)

## Main components

- app.py: FastAPI app with /ask endpoint
- runner.py: Runs agent graph step/logic
- agents/: router and worker agents
- services/: Integrations for 3rd-party APIs
- utils/: constants and prompt loader helpers
- prompts/: agent prompt templates

## Deploying

1. Copy your .env file as needed.
2. `docker compose up --build`
3. Visit http://localhost:8000/docs for Swagger API docs.

Optimize further by tweaking Gunicorn/worker count or Python base image.
