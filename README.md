# Nenad Kajgana — AI Assistant

A FastAPI + LangChain chatbot that answers questions about movies and music based on Nenad’s personal listening and watching data.
It uses LangGraph for agent orchestration, LangChain tools, Pinecone for vector storage, OpenAI embeddings / LLMs, Letterboxd and Spotify tools for personalized recommendations.

---

## Features

* Router / worker agents architecture (router, knowledge, main, music, movie).
* Retrieval from Pinecone vector store (knowledge about Nenad).
* Movie recommendations powered by Letterboxd tools.
* Music recommendations powered by Spotify (your account).
* Single endpoint to query the agent: `POST /ask`.
* Ready for local development and hosting (e.g. Render).

---

## Repo structure (high-level)

```
.
├─ app.py                       # FastAPI app
├─ runner.py                    # orchestration entry (run)
├─ agents/
│  ├─ router_agent.py
│  ├─ knowledge_agent.py
│  ├─ main_agent.py
│  ├─ music_recc_agent.py
│  └─ movie_recc_agent.py
├─ services/                    #letterbox, spotify services to fetch data
├─ tools/
│  ├─ spotify.py
│  └─ letterboxd.py
├─ utils/
│  ├─ constants.py              # embeddings, vector_store, llm, spotify client wrapper
│  └─ loader.py                 # prompt loader
├─ data.csv                     # CSV used to embed knowledge (optional)
├─ requirements.txt
└─ README.md
```

---

## Quick start — Backend (local)

> Assumes Python 3.10+ (adjust for your environment). Use a project `.venv`.

### 1. Create & activate venv

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Python deps

```bash
pip install -r requirements.txt
```

### 3. Environment variables

Create a `.env` file (don’t commit it) or set env vars in your host:

Required environment variables (example names — adapt to your `utils/constants.py`):

```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
INDEX_HOST=your-pinecone-host
PINECONE_INDEX=your-index-name
NAMESPACE=default
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REFRESH_TOKEN=...   # see "Spotify on Render" below
SPOTIFY_REDIRECT_URI=https://yourdomain.com/callback

# Chat tracking + persistence
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/chatbot
# Optional fallback if DATABASE_URL is invalid/unreachable (default: sqlite:///./chatbot.db)
DATABASE_FALLBACK_URL=sqlite:///./chatbot.db
RATE_LIMIT_REQUESTS=30
RATE_LIMIT_WINDOW_SECONDS=60

# Optional API hardening
TRUSTED_HOSTS=localhost,127.0.0.1,nenadkajgana.com
TRUST_X_FORWARDED_FOR=false  # set true only behind a trusted proxy

# Required for admin analytics authorization
MASTER_EMAIL=you@example.com
# Optional separate CD manager account; defaults to MASTER_EMAIL
CD_ADMIN_EMAIL=you@example.com

# Firebase token verification (choose one)
FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/firebase-admin.json
# OR
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```



### 4. Run the API

```bash
uvicorn app:app 
```

Open:

* Swagger UI: `http://127.0.0.1:8000/docs`
* Endpoint example: `POST http://127.0.0.1:8000/ask`

### 5. Example request

`POST /ask` JSON body:

```json
{
  "query": "Recommend me songs similar to the ones Nenad listens to",
  "history": "USER: previous question\nAI: previous answer",
  "visitor_id": "visitor_123",
  "chat_session_id": "session_abc",
  "email": "guest"
}
```

Response:

```json
{
  "answer": "...",
  "visitor_id": "visitor_123",
  "chat_session_id": "session_abc"
}
```

### Analytics endpoint (admin only)

`GET /analytics/summary` requires a valid Firebase `Authorization: Bearer <id_token>` header
for the configured `MASTER_EMAIL` (and a verified email claim). It returns visitor/session/message/event totals and a 24h window summary.

`POST /ask` now enforces session ownership: if a `chat_session_id` is reused with a different
`visitor_id`, the API responds with `409`.

Database startup is resilient: when `DATABASE_URL` is malformed or temporarily unavailable,
the backend automatically falls back to `DATABASE_FALLBACK_URL` (SQLite by default) and keeps serving requests.

### Private CD manager

The frontend route `/cdinja` signs in with Firebase Google authentication and manages the
SQL-backed `cds` table. Every request under `/cd-api` sends a Firebase ID token; the backend
verifies the token, its verified email claim, and an exact match with `CD_ADMIN_EMAIL` (or
`MASTER_EMAIL` when no separate CD email is set). A fresh database is seeded once with the
initial catalogue, with the first 32 entries marked as owned.

---

## Embedding / Vector store (add knowledge)

If you have a `data.csv` with `title, text` columns, use the provided helper to embed and upsert via your existing `vector_store`.

If you followed the recommended constants setup:


This will use the `OpenAIEmbeddings` and `PineconeVectorStore` objects you already initialize in `utils/constants.py`.

---
## Example `POST /ask` (curl)

```bash
curl -X POST "http://127.0.0.1:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Recommend me music similar to Nenad recent listens","history":"", "visitor_id":"visitor_123","chat_session_id":"session_abc","email":"guest"}'
```
