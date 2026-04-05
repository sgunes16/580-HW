# RAG580 — LangSmith evaluation pipeline

This folder holds the **offline evaluation** tooling: the question–answer dataset, custom LangSmith evaluators, baseline runs, and multi-configuration sweeps.

## Prerequisites

- **Ollama** running with the same embedding and chat models you use in the app (see repo root `README.md`).
- **PDFs** indexed under `data/pdfs/` (the evaluators call `answer_question()` which retrieves from Chroma).
- Python deps from `backend/requirements.txt` (includes `langsmith`).

Environment variables are read from the **repository root** `.env` (and optionally `backend/.env`). Copy from `.env.example` at the repo root.

| Variable | Purpose |
|----------|---------|
| `LANGSMITH_TRACING` | `true` to enable tracing |
| `LANGSMITH_API_KEY` | Required for LangSmith dataset upload and `evaluate()` runs |
| `LANGSMITH_PROJECT` | Project name (default `rag580`) |
| `LANGSMITH_ENDPOINT` | Optional; default `https://api.smith.langchain.com` |
| `LANGSMITH_WORKSPACE_ID` | Optional workspace id |
| `OLLAMA_BASE_URL` | If Ollama is not on `http://127.0.0.1:11434` |

Run scripts with the backend venv so imports resolve:

```bash
cd /path/to/580-HW
backend/.venv/bin/python eval/langsmith_eval.py
```

## Dataset

- **`eval_dataset.json`** — `items[]` with `question`, `reference_answer`, `difficulty`, and optional `source_pdf` / `reference_pages` for traceability.

If a LangSmith dataset exists but has **no examples**, `ensure_langsmith_dataset` repopulates it from this file.

## Custom evaluators (`langsmith_eval.py`)

Four programmatic scores (each returns a `key` / `score` pair for LangSmith):

1. **correctness** — token-level overlap / F1 style alignment vs reference answer  
2. **relevance** — whether the answer addresses the question (lexical overlap)  
3. **groundedness** — support ratio vs retrieved-style signals (reduces “made up” drift)  
4. **conciseness** — rewards shorter answers without empty outputs  

The `predict()` target calls **`answer_question()`** from the backend RAG pipeline. Runtime **chunk_size**, **chunk_overlap**, and **top_k** are attached to LangSmith **metadata** on baseline experiments and are also updated in the sweep.

### Baseline evaluation

```bash
backend/.venv/bin/python eval/langsmith_eval.py
```

| Flag | Description |
|------|-------------|
| `--dataset-name` | LangSmith dataset name (default `rag580-eval`) |
| `--report-path` | Output markdown (default `eval/langsmith_baseline_report.md`) |
| `--skip-langsmith` | Local metrics + report only; no API calls |

Without `LANGSMITH_API_KEY`, the script still runs **local** evaluation and writes the report.

### Configuration sweep (`langsmith_config_sweep.py`)

Runs **10** default experiments (chunk size 500→5000 with paired overlap and `top_k`). For each config it:

- Updates `runtime_settings` (chunk / overlap / top_k)
- Uses an **isolated Chroma directory** under `data/chroma_sweeps/c{size}_o{overlap}/` (skips re-index if that folder already exists)
- Re-indexes all PDFs when needed (progress logged to the terminal)
- Runs the full evaluator suite as a **separate LangSmith experiment** (unless skipped)
- Writes **`eval/langsmith_config_sweep_report.md`** with a comparison table and a weighted “best config” summary

```bash
backend/.venv/bin/python eval/langsmith_config_sweep.py
```

| Flag | Description |
|------|-------------|
| `--dataset-name` | Same as baseline (default `rag580-eval`) |
| `--config-file` | JSON array: `[{"chunk_size", "chunk_overlap", "top_k"}, ...]` |
| `--report-path` | Output markdown path |
| `--skip-langsmith` | Sweep locally only (no LangSmith experiments) |

**Note:** Sweep is much slower than baseline because chunking changes require re-embedding. The app’s main Chroma path is restored after the sweep finishes.


## Related files

- `manual_test_results.md` — manual UI/chat test log template  
- Repo root `README.md` — full stack setup and Docker  
