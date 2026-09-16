# Nenad Kajgana — AI Assistant

A FastAPI + LangGraph chatbot that answers questions about Nenad, movies, and music based on his personal data.
An explicit supervisor/tool loop retrieves read-only facts as needed and produces one final response.

---

## Features

* Explicit LangGraph `StateGraph` with one supervisor and one tool-execution node.
* Structured knowledge, movie, music, and CD retrieval capabilities.
* Separate cached guest and admin graphs with fixed tool allowlists.
* Admin chat mutations authorized only by a verified Firebase `MASTER_EMAIL` claim.
* Single endpoint to query the agent: `POST /ask`.
* Ready for local development and hosting (e.g. Render).

---

## Assistant graph

```mermaid
flowchart LR
    START([START]) --> supervisor[Supervisor]
    supervisor -->|Requests one or more capabilities| tools[ToolNode]
    tools -->|Returns structured context| supervisor
    supervisor -->|No capability requests; final answer ready| END([END])
```

The guest graph binds only the knowledge, music, and movie read-only capabilities. The admin graph
uses the same loop but additionally binds CD creation, CD ownership updates, and knowledge upserts.
The two variants are compiled once and cached with separate fixed allowlists.

---

## Repo structure (high-level)

```
.
├─ app.py                       # FastAPI app
├─ runner.py                    # orchestration entry (run)
├─ agents/
│  └─ supervisor_agent.py       # one model-driven supervisor node
├─ graphs/
│  └─ user_chat.py              # supervisor ↔ tool loop and allowlists
├─ prompts/
│  └─ supervisor.mustache
├─ services/                    # data integrations
├─ tools/
│  ├─ index.py                  # knowledge retrieval
│  ├─ spotify.py                # normalized music context
│  ├─ letterboxd.py             # normalized movie context
│  └─ master_tools.py           # admin-only mutations
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

# Monthly visitor-question report via Resend
RESEND_API_KEY=re_...
MONTHLY_REPORT_TO=reports-recipient@example.com
MONTHLY_REPORT_FROM="Portfolio Reports <questions@reports.nenadkajgana.com>"
MONTHLY_REPORT_START_MONTH=2026-09
MONTHLY_REPORT_ENABLED=false

# Optional API hardening
TRUSTED_HOSTS=localhost,127.0.0.1,nenadkajgana.com
TRUST_X_FORWARDED_FOR=false  # set true only behind a trusted proxy

# Required for admin analytics and protected chat actions
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

The request `email` field remains accepted for compatibility but never grants access. Protected chat
actions are exposed only when the bearer token is valid, its email is verified, and its normalized
email exactly matches `MASTER_EMAIL`. Guests and all other authenticated users receive the read-only graph.

### Analytics endpoint (admin only)

`GET /analytics/summary` requires a valid Firebase `Authorization: Bearer <id_token>` header
for the configured `MASTER_EMAIL` (and a verified email claim). It returns visitor/session/message/event totals and a 24h window summary.

### Monthly visitor-question report

The backend records every accepted `/ask` submission before processing it. The report covers the
previous UTC calendar month, groups questions by visitor and session, and attaches all questions as
CSV. Failed submissions are labeled with their outcome. Empty months do not send an email.

Preview a month without sending or writing report state:

```bash
docker exec portfolio-be python -m monthly_report preview 2026-09
```

Send a synthetic delivery test (this ignores `MONTHLY_REPORT_ENABLED`):

```bash
docker exec portfolio-be python -m monthly_report send-test
```

After the test arrives, set `MONTHLY_REPORT_ENABLED=true` in `.env`, redeploy the backend so the
container receives the setting, and install the hourly persistent systemd timer:

```bash
./scripts/install_monthly_report_timer.sh
```

The installer creates a persistent user timer by default and installs a system timer when run as
root. The user account must be allowed to run Docker and have systemd lingering enabled.

Inspect scheduling and delivery logs with:

```bash
systemctl --user status portfolio-monthly-report.timer
journalctl --user -u portfolio-monthly-report.service
```

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
