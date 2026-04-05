# RAG580 — Web backend (FastAPI)

HTTP API for document ingestion, vector search, chat (including streaming), persisted conversations, and runtime RAG settings. The React app (Vite) proxies `/api` here in development.

## Requirements

- Python **3.11+** (see repo root README if LangChain warns on very new Python)
- **Ollama** running for embeddings and LLM calls
- Optional: LangSmith env vars for tracing (see below)

## Setup

From the **repository root** (recommended so paths like `data/` resolve correctly):

```bash
cp .env.example .env
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **API:** `http://127.0.0.1:8000`  
- **OpenAPI:** `http://127.0.0.1:8000/docs`  
- **Health:** `GET /health`

`pydantic-settings` loads `.env` from **repo root** first, then `backend/.env`.

## Environment variables (`app/config.py`)

| Variable | Description |
|----------|-------------|
| `OLLAMA_BASE_URL` | Ollama HTTP API (default `http://127.0.0.1:11434`) |
| `LANGSMITH_TRACING` | Enable LangSmith tracing on startup |
| `LANGSMITH_API_KEY` | LangSmith API key |
| `LANGSMITH_PROJECT` | Project name |
| `LANGSMITH_ENDPOINT` | API endpoint (optional) |
| `LANGSMITH_WORKSPACE_ID` | Workspace id (optional) |

Default model names (overridable via **Settings** API / `data/runtime_settings.json`): embedding `nomic-embed-text`, LLM `llama3.2`.

## Data layout (under repo root)

| Path | Purpose |
|------|---------|
| `data/pdfs/` | Uploaded PDFs |
| `data/chroma/` | Default Chroma persist directory |
| `data/runtime_settings.json` | Chunk size, overlap, top_k, model names |
| `data/app.db` | Chat conversations and messages |

## Route map (`app/main.py`)

All JSON routes are under **`/api`** except `/health`.

### Documents

- `GET /api/documents/list` — PDFs plus index status, chunk counts, orphaned index hints  
- Upload / reindex endpoints as implemented in `app/api/routes/documents.py`  
- Index deletion: per-file and delete-all (see OpenAPI)

### Chat

- `POST /api/chat` — non-streaming JSON answer + sources + `conversation_id`  
- `POST /api/chat/stream` — **NDJSON** stream (`start`, `delta`, `done`, `error` events)

### Conversations

- `GET /api/chats` — list stored threads  
- `GET /api/chats/{id}/messages` — load messages (includes stored source refs when present)  
- `DELETE /api/chats/{id}` — delete thread  

### Settings

- `GET` / `PUT` (or as defined) for `chunk_size`, `chunk_overlap`, `top_k`, models — see `/docs`

## Core modules

- `app/services/rag_pipeline.py` — retrieval, memory compaction, LLM calls; LangSmith run metadata for chunk settings when tracing is on  
- `app/services/ingest.py` — PDF chunking and Chroma writes  
- `app/db/chat_db.py` — conversation persistence  
- `app/core/runtime_settings.py` — read/write `runtime_settings.json`  
- `app/core/langsmith_setup.py` — tracing configuration at startup  

## Docker

The repo root `docker-compose.yml` builds this service; Ollama is expected on the host. Set `OLLAMA_BASE_URL` appropriately (e.g. `http://host.docker.internal:11434`).

## Evaluation scripts

Offline LangSmith / local eval lives in **`../eval/`** — see `eval/README.md`.
