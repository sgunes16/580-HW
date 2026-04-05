# Course RAG — LangChain, Ollama, Chroma

Retrieval-Augmented Generation over software engineering course PDFs. **FastAPI** backend, **React + Chakra UI** frontend, **Chroma** vector store, embeddings and generation via **Ollama**.

## Requirements

- Python 3.11+ (3.12 recommended; avoid bleeding-edge Python if LangChain warns about Pydantic)
- Node.js 18+
- [Ollama](https://ollama.com) installed

## Run Ollama first (required)

**Indexing and chat will not work unless Ollama is running.** Do this before starting the backend or using Docker:

1. **Start Ollama** — open the Ollama app (macOS/Windows) or run `ollama serve` in a terminal and leave it running.
2. **Pull the models** you use in **Settings** (defaults below). Without this, embedding and LLM calls fail.

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
```

3. **Check** — `ollama list` should show those models; the API must reach `http://127.0.0.1:11434` (or your `OLLAMA_BASE_URL` in Docker).

If Ollama is not running, you will see connection errors when indexing or chatting.

## Backend (local)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API: `http://127.0.0.1:8000` — OpenAPI: `/docs`

## Frontend (local)

```bash
cd frontend
npm install
npm run dev
```

Browser: `http://localhost:5173` (Vite proxies `/api` to the backend.)

## Docker Compose

**Start Ollama on the host first** (same as above); containers do not bundle Ollama.

Build and run API + static UI (nginx on port **8080**). The API expects Ollama on the **host** at `http://host.docker.internal:11434` (default `OLLAMA_BASE_URL`).

```bash
docker compose up --build
```

- UI: `http://localhost:8080`
- API (direct): `http://localhost:8000`

Mount `./data` into the API container for PDFs, Chroma persistence, and `runtime_settings.json`.

## Usage

1. **Settings**: Adjust `chunk_size`, `chunk_overlap`, `top_k`, and model names (must match `ollama list`).
2. **Documents**: Upload PDFs. Indexing runs **in the background**; the UI shows a **progress bar** and status text while embeddings are computed.
   - **Index this file** — only re-embeds that PDF (removes its old vectors, then adds new chunks).
   - **Index all PDFs** — walks every file in `data/pdfs/` the same way (per-file replace).
   - **Full reset** — deletes the entire Chroma directory, then indexes all PDFs (use after changing the embedding model or if the store is corrupted).
3. **Chat**: Multi-turn **conversation memory**. Each request sends the current `question` plus prior `history` (user/assistant turns). The backend targets a **~50k-token** context window: retrieved document text and the new question consume part of the budget; remaining space is for prior turns. When history exceeds that budget, **older turns are summarized** with a second LLM call (same Ollama model, lower temperature), then recent turns are kept verbatim. The UI shows a short notice when compaction runs. Use **Clear chat** to reset the thread (client-side only).

PDFs are stored under `data/pdfs/`; Chroma data under `data/chroma/`. **Chat history** is stored in SQLite at `data/app.db` (conversations + messages). Each reply returns a `conversation_id`; send it on the next request to append to the same thread. The UI lists saved chats and supports delete.

### API (chat)

- `POST /api/chat` — JSON `{ "question": "…", "history": [ … ], "conversation_id": null | "<uuid>" }`. Omit `conversation_id` to start a new stored thread; reuse the id from the previous response to append. Response adds `conversation_id` and `context_usage` (estimated token breakdown vs the ~50k window for the UI gauge).
- `GET /api/chats` — `{ "conversations": [ { "id", "title", "created_at", "updated_at", "message_count" } ] }`.
- `GET /api/chats/{id}/messages` — `{ "conversation_id", "messages": [ { "id", "role", "content", "created_at" } ] }`.
- `DELETE /api/chats/{id}` — remove a conversation and its messages.

### API (indexing jobs)

- `POST /api/documents/reindex` — JSON body `{ "filename": null | "my.pdf", "reset": false }`. Returns `{ "job_id", "status": "queued" }`.
- `GET /api/documents/reindex/jobs/{job_id}` — `{ "status": "running"|"completed"|"failed", "progress": 0-100, "message", "error", "result" }`.

Server logs (terminal where `uvicorn` runs) record stack traces for unexpected errors; connection issues to Ollama return **503** with a clear message when handled by the chat/reindex error mapper.

## Evaluation

- [`eval/eval_dataset.json`](eval/eval_dataset.json): 20 question–answer pairs (difficulty labels); fill after PDFs are available.
- [`eval/manual_test_results.md`](eval/manual_test_results.md): Template for at least 5 manual test runs.

## Troubleshooting

**Indexing fails with 503 / “Cannot reach Ollama”**

Indexing calls Ollama for embeddings. Start the Ollama app, then pull the models you set under **Settings** (for example `ollama pull nomic-embed-text` and `ollama pull llama3.2`).  
If you use Docker for the API, set `OLLAMA_BASE_URL` to `http://host.docker.internal:11434` (see `docker-compose.yml`) and keep Ollama running on the host.

**500 Internal Server Error**

Check the **uvicorn** terminal: errors are logged with a full traceback (`Service error (returning 500)` or `Reindex job … failed`). Background indexing failures appear in the job status as `failed` with an `error` string; the UI shows that message.

**Port 5173 already in use (local Vite):**

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN -t | xargs kill -9
```
