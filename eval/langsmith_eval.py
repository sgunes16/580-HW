from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from langsmith import Client, evaluate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.langsmith_setup import configure_langsmith  # noqa: E402
from app.core.runtime_settings import get_settings  # noqa: E402
from app.services.rag_pipeline import answer_question  # noqa: E402

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
}


def load_eval_items() -> list[dict[str, Any]]:
    data = json.loads((PROJECT_ROOT / "eval" / "eval_dataset.json").read_text())
    return data["items"]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def content_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", normalize_text(text))
        if token not in STOPWORDS and len(token) > 1
    ]


def token_f1(prediction: str, reference: str) -> float:
    pred = content_tokens(prediction)
    ref = content_tokens(reference)
    if not pred or not ref:
        return 0.0
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    overlap = sum((pred_counts & ref_counts).values())
    if overlap == 0:
        return 0.0
    precision = overlap / max(len(pred), 1)
    recall = overlap / max(len(ref), 1)
    return 2 * precision * recall / (precision + recall)


def key_overlap(question: str, answer: str) -> float:
    q_tokens = set(content_tokens(question))
    a_tokens = set(content_tokens(answer))
    if not q_tokens:
        return 0.0
    return len(q_tokens & a_tokens) / len(q_tokens)


def support_ratio(answer: str, sources: list[dict[str, Any]], reference: str) -> float:
    answer_tokens = content_tokens(answer)
    if not answer_tokens:
        return 0.0
    source_text = " ".join((s.get("snippet") or "") for s in sources or [])
    support_tokens = set(content_tokens(source_text) + content_tokens(reference))
    if not support_tokens:
        return 0.0
    supported = sum(1 for token in answer_tokens if token in support_tokens)
    return supported / len(answer_tokens)


def conciseness_score(answer: str, reference: str) -> float:
    answer_len = max(len(content_tokens(answer)), 1)
    ref_len = max(len(content_tokens(reference)), 1)
    ratio = answer_len / ref_len
    if ratio <= 1.4:
        return 1.0
    if ratio <= 1.8:
        return 0.8
    if ratio <= 2.3:
        return 0.6
    if ratio <= 3.0:
        return 0.35
    return 0.1


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def predict(inputs: dict[str, Any]) -> dict[str, Any]:
    question = inputs["question"]
    rs = get_settings()
    out = answer_question(question, history=[])
    return {
        "answer": out.get("answer") or "",
        "sources": out.get("sources") or [],
        "context_usage": out.get("context_usage") or {},
        "difficulty": inputs.get("difficulty"),
        "settings": {
            "chunk_size": rs.chunk_size,
            "chunk_overlap": rs.chunk_overlap,
            "top_k": rs.top_k,
        },
    }


def correctness_evaluator(run: Any, example: Any) -> dict[str, float]:
    outputs = _get(run, "outputs", {}) or {}
    expected = (_get(example, "outputs", {}) or {}).get("answer", "")
    score = token_f1(outputs.get("answer", ""), expected)
    return {"key": "correctness", "score": round(score, 4)}


def relevance_evaluator(run: Any, example: Any) -> dict[str, float]:
    inputs = _get(run, "inputs", {}) or {}
    outputs = _get(run, "outputs", {}) or {}
    score = key_overlap(inputs.get("question", ""), outputs.get("answer", ""))
    return {"key": "relevance", "score": round(score, 4)}


def groundedness_evaluator(run: Any, example: Any) -> dict[str, float]:
    outputs = _get(run, "outputs", {}) or {}
    expected = (_get(example, "outputs", {}) or {}).get("answer", "")
    score = support_ratio(
        outputs.get("answer", ""),
        outputs.get("sources", []) or [],
        expected,
    )
    return {"key": "groundedness", "score": round(score, 4)}


def conciseness_evaluator(run: Any, example: Any) -> dict[str, float]:
    outputs = _get(run, "outputs", {}) or {}
    expected = (_get(example, "outputs", {}) or {}).get("answer", "")
    score = conciseness_score(outputs.get("answer", ""), expected)
    return {"key": "conciseness", "score": round(score, 4)}


EVALUATORS = [
    correctness_evaluator,
    relevance_evaluator,
    groundedness_evaluator,
    conciseness_evaluator,
]


def ensure_langsmith_dataset(client: Client, dataset_name: str, items: list[dict[str, Any]]):
    dataset = next(client.list_datasets(dataset_name=dataset_name), None)
    if dataset is None:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="RAG580 evaluation dataset uploaded from eval/eval_dataset.json",
        )
        client.create_examples(
            dataset_id=dataset.id,
            inputs=[
                {"question": item["question"], "difficulty": item["difficulty"]}
                for item in items
            ],
            outputs=[
                {
                    "answer": item["reference_answer"],
                    "difficulty": item["difficulty"],
                }
                for item in items
            ],
        )
    return dataset


def run_local_eval(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for item in items:
        inputs = {"question": item["question"], "difficulty": item["difficulty"]}
        outputs = predict(inputs)
        run = {"inputs": inputs, "outputs": outputs}
        example = {"outputs": {"answer": item["reference_answer"]}}
        metrics: dict[str, float] = {}
        for evaluator in EVALUATORS:
            metrics.update(evaluator(run, example))
        records.append(
            {
                "id": item["id"],
                "difficulty": item["difficulty"],
                "question": item["question"],
                "reference_answer": item["reference_answer"],
                "prediction": outputs["answer"],
                "sources": outputs.get("sources", []),
                **metrics,
            }
        )
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = ["correctness", "relevance", "groundedness", "conciseness"]

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    overall = {
        metric: mean([float(r[metric]) for r in records])
        for metric in metric_names
    }
    by_difficulty: dict[str, dict[str, float]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["difficulty"]].append(record)
    for difficulty, rows in grouped.items():
        by_difficulty[difficulty] = {
            metric: mean([float(r[metric]) for r in rows]) for metric in metric_names
        }
        by_difficulty[difficulty]["count"] = len(rows)

    failures = sorted(
        records,
        key=lambda r: (
            r["correctness"],
            r["groundedness"],
            r["relevance"],
            -len(r["prediction"]),
        ),
    )[:3]
    return {
        "overall": overall,
        "by_difficulty": by_difficulty,
        "failures": failures,
    }


def build_report(
    summary: dict[str, Any],
    *,
    dataset_name: str,
    langsmith_status: str,
) -> str:
    overall = summary["overall"]
    by_difficulty = summary["by_difficulty"]
    failures = summary["failures"]

    lines = [
        "# LangSmith Baseline Evaluation",
        "",
        f"- Dataset: `{dataset_name}`",
        f"- LangSmith upload / experiment status: {langsmith_status}",
        "- Custom evaluators: correctness, relevance, groundedness (hallucination risk inverse), conciseness",
        "",
        "## Overall Metrics",
        "",
        "| Metric | Score |",
        "|---|---:|",
        f"| correctness | {overall['correctness']:.4f} |",
        f"| relevance | {overall['relevance']:.4f} |",
        f"| groundedness | {overall['groundedness']:.4f} |",
        f"| conciseness | {overall['conciseness']:.4f} |",
        "",
        "## By Difficulty",
        "",
        "| Difficulty | Count | Correctness | Relevance | Groundedness | Conciseness |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for difficulty in ("easy", "medium", "hard"):
        row = by_difficulty.get(difficulty, {})
        lines.append(
            f"| {difficulty} | {row.get('count', 0)} | "
            f"{row.get('correctness', 0):.4f} | {row.get('relevance', 0):.4f} | "
            f"{row.get('groundedness', 0):.4f} | {row.get('conciseness', 0):.4f} |"
        )

    lines.extend(
        [
            "",
            "## Failure Cases",
            "",
        ]
    )
    for idx, failure in enumerate(failures, 1):
        lines.extend(
            [
                f"### Failure {idx}",
                "",
                f"- Question: {failure['question']}",
                f"- Difficulty: `{failure['difficulty']}`",
                f"- correctness: {failure['correctness']:.4f}",
                f"- relevance: {failure['relevance']:.4f}",
                f"- groundedness: {failure['groundedness']:.4f}",
                f"- conciseness: {failure['conciseness']:.4f}",
                f"- Model answer: {failure['prediction']}",
                f"- Reference answer: {failure['reference_answer']}",
                (
                    "- Discussion: The baseline answer either missed a key detail from the reference, "
                    "introduced unsupported framing, or expanded beyond what the retrieved evidence clearly grounded."
                ),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-name", default="rag580-eval")
    parser.add_argument(
        "--report-path",
        default=str(PROJECT_ROOT / "eval" / "langsmith_baseline_report.md"),
    )
    parser.add_argument("--skip-langsmith", action="store_true")
    args = parser.parse_args()

    configure_langsmith()
    items = load_eval_items()
    rs = get_settings()

    langsmith_status = "skipped"
    if not args.skip_langsmith and os.environ.get("LANGSMITH_API_KEY"):
        client = Client()
        ensure_langsmith_dataset(client, args.dataset_name, items)
        evaluate(
            predict,
            data=args.dataset_name,
            evaluators=EVALUATORS,
            experiment_prefix="rag580-baseline",
            metadata={
                "app": "rag580",
                "dataset_items": len(items),
                "chunk_size": rs.chunk_size,
                "chunk_overlap": rs.chunk_overlap,
                "top_k": rs.top_k,
            },
        )
        langsmith_status = "completed"
    elif not args.skip_langsmith:
        langsmith_status = "not run (missing LANGSMITH_API_KEY)"

    records = run_local_eval(items)
    summary = summarize(records)
    report = build_report(
        summary,
        dataset_name=args.dataset_name,
        langsmith_status=langsmith_status,
    )
    Path(args.report_path).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
