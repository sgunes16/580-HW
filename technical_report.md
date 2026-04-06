# Technical Report: RAG580

## 1. Project Scope

This project implements a Retrieval-Augmented Generation (RAG) system over course PDFs related to software engineering, data science, and data systems. The system combines a FastAPI backend, a React frontend, Ollama-based generation and embedding models, a Chroma vector store, and LangSmith-based evaluation.

The main goals of the project were:

- build an end-to-end PDF-based RAG pipeline
- support interactive chat with saved conversations and source references
- evaluate the system systematically with LangSmith
- compare retrieval configurations and identify the strongest setup

## 2. Repository Deliverables

The repository includes:

- application code for the backend and frontend
- LangSmith evaluation scripts and reports
- manual test results
- setup and reproduction instructions in `README.md`, `backend/README.md`, and `eval/README.md`

Important note:

- the source course PDFs should also be submitted separately if they are not committed to the repository
- to reproduce indexing and evaluation, the PDFs must be placed under `data/pdfs/`

## 3. System Architecture

The RAG pipeline works as follows:

1. PDF files are uploaded or copied into `data/pdfs/`.
2. The ingestion pipeline splits PDFs into chunks using configurable `chunk_size` and `chunk_overlap`.
3. Chunks are embedded with Ollama and stored in Chroma.
4. At question time, the system retrieves the top `k` chunks and builds a prompt with conversation history.
5. The LLM generates an answer, and the UI displays the reply together with source references.
6. LangSmith traces record runs, metadata, and evaluator outputs for offline analysis.

## 4. Evaluation Setup

### Dataset

The evaluation dataset is stored in `eval/eval_dataset.json`. It contains question-answer pairs labeled by difficulty and grounded in the course materials.

### Custom evaluators

The LangSmith pipeline uses four programmatic evaluators:

- `correctness`: overlap-based alignment with the reference answer
- `relevance`: how well the answer addresses the question
- `groundedness`: how well the answer stays supported by the retrieved material
- `conciseness`: whether the answer stays compact instead of over-explaining

### Baseline experiment

The baseline report was generated from the LangSmith baseline run with:

- `chunk_size = 1500`
- `chunk_overlap = 180`
- `top_k = 4`

Baseline metrics:


| Metric       | Score  |
| ------------ | ------ |
| correctness  | 0.1435 |
| relevance    | 0.7294 |
| groundedness | 0.2708 |
| conciseness  | 0.1625 |


Interpretation:

- relevance is the strongest metric, which means the system usually stays on-topic
- correctness and groundedness are still weak, which shows that the model often answers with plausible but only partially supported content
- conciseness is also low, indicating that the model tends to add generic explanation instead of giving short, textbook-aligned answers

## 5. Configuration Sweep

To optimize retrieval quality, I ran a 10-experiment LangSmith sweep with chunk sizes from `500` to `2000`. Each run also adjusted `chunk_overlap` and `top_k`.

Tested configurations:


| Experiment | chunk_size | chunk_overlap | top_k |
| ---------- | ---------- | ------------- | ----- |
| 1          | 500        | 80            | 3     |
| 2          | 650        | 90            | 3     |
| 3          | 800        | 100           | 4     |
| 4          | 950        | 120           | 4     |
| 5          | 1100       | 130           | 4     |
| 6          | 1250       | 150           | 4     |
| 7          | 1400       | 170           | 4     |
| 8          | 1550       | 190           | 5     |
| 9          | 1750       | 210           | 5     |
| 10         | 2000       | 240           | 5     |


The LangSmith comparison dashboard showed the following rounded scores:


| Experiment   | conciseness | correctness | groundedness | relevance |
| ------------ | ----------- | ----------- | ------------ | --------- |
| 1 (`c500`)   | 0.23        | 0.24        | 0.54         | 0.77      |
| 2 (`c650`)   | 0.25        | 0.22        | 0.50         | 0.74      |
| 3 (`c800`)   | 0.19        | 0.21        | 0.52         | 0.77      |
| 4 (`c950`)   | 0.15        | 0.19        | 0.47         | 0.78      |
| 5 (`c1100`)  | 0.15        | 0.19        | 0.48         | 0.77      |
| 6 (`c1250`)  | 0.17        | 0.19        | 0.47         | 0.77      |
| 7 (`c1400`)  | 0.17        | 0.20        | 0.51         | 0.77      |
| 8 (`c1550`)  | 0.16        | 0.21        | 0.52         | 0.76      |
| 9 (`c1750`)  | 0.18        | 0.22        | 0.51         | 0.77      |
| 10 (`c2000`) | 0.21        | 0.22        | 0.51         | 0.76      |


## 6. Best Configuration

Based on the comparison table, the strongest overall configuration is:

- `chunk_size = 500`
- `chunk_overlap = 80`
- `top_k = 3`

Why this setting is the best:

- it achieved the highest displayed `correctness` score in the sweep
- it also produced the highest `groundedness` score in the comparison
- its `relevance` remained competitive with the larger chunk settings
- its `conciseness` was better than most alternatives

This result suggests that smaller chunks improve retrieval precision for this dataset. The course questions often ask for narrow definitions, named concepts, and specific textbook taxonomies. Larger chunks appear to introduce too much surrounding context, which makes the model more likely to answer with broad background explanations instead of the exact concept requested.

## 7. Failure Analysis

The baseline and sweep results show a consistent pattern:

- the model usually understands the topic of the question
- the model often fails to match the exact textbook definition
- the answer sometimes expands into generic data-engineering explanations
- this lowers correctness and groundedness even when relevance remains acceptable

Representative failure types:

1. **Term misdefinition**
  Terms like *bursting* were interpreted as system load spikes instead of the course-specific record transformation meaning.
2. **Generic reformulation instead of exact retrieval-aligned answer**
  For concepts like *Transitive Closure*, the answer drifted toward broad graph-style explanations rather than the specific preprocessing and clustering interpretation used in the material.
3. **Substituting plausible concepts for the canonical list**
  For questions such as the *undercurrents* of the data engineering lifecycle, the answer listed sensible ideas but failed to reproduce the exact textbook categories.

## 8. Main Conclusion

 The current RAG pipeline retrieves relevant material, but larger contexts encourage the model to generalize too much. The sweep results indicate that smaller chunking improves factual precision and grounding for this dataset.

The strongest next steps would be:

- keep the smaller chunk range as the default for this corpus
- further tighten the answer prompt so the model prefers short definition-style responses
- improve retrieval filtering so only the most directly relevant chunks are placed into the final context

### Included LangSmith Screenshots

#### Dataset view

![LangSmith dataset view](<screenshots/langsmith/Screenshot 2026-04-06 at 23-23-40 rag580-eval - LangSmith.png>)

#### Comparison view

![LangSmith experiment view](<screenshots/langsmith/Screenshot 2026-04-06 at 23-25-16 rag580-eval - LangSmith.png>)

#### experiment view

![LangSmith trace detail](<screenshots/langsmith/Screenshot 2026-04-06 at 23-24-58 rag580-sweep-c2000-o240-k5-3b5ea2ab - LangSmith.png>)

#### Trace or evaluator detail view

![LangSmith sweep comparison](<screenshots/langsmith/Screenshot 2026-04-06 at 23-24-37 rag580-sweep-c2000-o240-k5-3b5ea2ab - LangSmith.png>)


## 9. Reproducibility

To reproduce the full pipeline:

1. place the course PDFs in `data/pdfs/`
2. start Ollama and install the required models
3. run the backend and frontend locally or with Docker
4. index the PDFs
5. run `backend/.venv/bin/python eval/langsmith_eval.py`
6. run `backend/.venv/bin/python eval/langsmith_config_sweep.py`
7. collect the LangSmith dashboard screenshots listed above


