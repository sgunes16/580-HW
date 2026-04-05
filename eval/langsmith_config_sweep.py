from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from langsmith import Client, evaluate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.langsmith_setup import configure_langsmith  # noqa: E402
from app.config import settings as app_settings  # noqa: E402
from app.core.runtime_settings import get_settings, save_settings, update_settings  # noqa: E402
from app.services import ingest  # noqa: E402
from app.services import vector_store as vs_mod  # noqa: E402
from langsmith_eval import (  # noqa: E402
    EVALUATORS,
    ensure_langsmith_dataset,
    load_eval_items,
    predict,
    run_local_eval,
    summarize,
)

DEFAULT_CONFIGS: list[dict[str, int]] = [
    {"chunk_size": 500, "chunk_overlap": 80, "top_k": 3},
    {"chunk_size": 1000, "chunk_overlap": 120, "top_k": 4},
    {"chunk_size": 1500, "chunk_overlap": 180, "top_k": 4},
    {"chunk_size": 2000, "chunk_overlap": 240, "top_k": 5},
    {"chunk_size": 2500, "chunk_overlap": 300, "top_k": 5},
    {"chunk_size": 3000, "chunk_overlap": 360, "top_k": 6},
    {"chunk_size": 3500, "chunk_overlap": 420, "top_k": 6},
    {"chunk_size": 4000, "chunk_overlap": 480, "top_k": 7},
    {"chunk_size": 4500, "chunk_overlap": 540, "top_k": 7},
    {"chunk_size": 5000, "chunk_overlap": 600, "top_k": 8},
]


def load_configs(path: str | None) -> list[dict[str, int]]:
    if not path:
        return deepcopy(DEFAULT_CONFIGS)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("config file must contain a non-empty JSON array")
    configs = []
    for item in data:
        configs.append(
            {
                "chunk_size": int(item["chunk_size"]),
                "chunk_overlap": int(item["chunk_overlap"]),
                "top_k": int(item["top_k"]),
            }
        )
    return configs


def score_summary(summary: dict[str, Any]) -> float:
    overall = summary["overall"]
    return round(
        overall["correctness"] * 0.4
        + overall["groundedness"] * 0.3
        + overall["relevance"] * 0.2
        + overall["conciseness"] * 0.1,
        4,
    )


def format_config(config: dict[str, int]) -> str:
    return (
        f"chunk_size={config['chunk_size']}, "
        f"chunk_overlap={config['chunk_overlap']}, "
        f"top_k={config['top_k']}"
    )


def make_progress_logger(run_idx: int, total_runs: int):
    last_pct: int | None = None
    last_msg = ""

    def _log(pct: float, msg: str) -> None:
        nonlocal last_pct, last_msg
        pct_int = int(round(pct))
        if pct_int == last_pct and msg == last_msg:
            return
        last_pct = pct_int
        last_msg = msg
        print(
            f"[{run_idx}/{total_runs}] indexing {pct_int:>3}% | {msg}",
            flush=True,
        )

    return _log


def get_sweep_chroma_dir(config: dict[str, int]) -> Path:
    return (
        PROJECT_ROOT
        / "data"
        / "chroma_sweeps"
        / f"c{config['chunk_size']}_o{config['chunk_overlap']}"
    )


def has_existing_index(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def build_report(
    results: list[dict[str, Any]],
    *,
    dataset_name: str,
    langsmith_enabled: bool,
) -> str:
    best = max(results, key=lambda item: item["composite_score"])
    lines = [
        "# LangSmith Configuration Sweep",
        "",
        f"- Dataset: `{dataset_name}`",
        f"- LangSmith experiments executed: {'yes' if langsmith_enabled else 'no'}",
        f"- Configurations tested: {len(results)}",
        "- Ranking score: `0.4*correctness + 0.3*groundedness + 0.2*relevance + 0.1*conciseness`",
        "",
        "## Experiment Summary",
        "",
        "| # | chunk_size | chunk_overlap | top_k | correctness | relevance | groundedness | conciseness | composite |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    ranked = sorted(results, key=lambda item: item["composite_score"], reverse=True)
    for idx, item in enumerate(ranked, 1):
        config = item["config"]
        overall = item["summary"]["overall"]
        lines.append(
            f"| {idx} | {config['chunk_size']} | {config['chunk_overlap']} | {config['top_k']} | "
            f"{overall['correctness']:.4f} | {overall['relevance']:.4f} | "
            f"{overall['groundedness']:.4f} | {overall['conciseness']:.4f} | "
            f"{item['composite_score']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Best Configuration",
            "",
            f"- Best config: `{format_config(best['config'])}`",
            f"- Composite score: `{best['composite_score']:.4f}`",
            f"- correctness: `{best['summary']['overall']['correctness']:.4f}`",
            f"- relevance: `{best['summary']['overall']['relevance']:.4f}`",
            f"- groundedness: `{best['summary']['overall']['groundedness']:.4f}`",
            f"- conciseness: `{best['summary']['overall']['conciseness']:.4f}`",
            "",
            "## Difficulty Breakdown For Best Config",
            "",
            "| Difficulty | Count | Correctness | Relevance | Groundedness | Conciseness |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for difficulty in ("easy", "medium", "hard"):
        row = best["summary"]["by_difficulty"].get(difficulty, {})
        lines.append(
            f"| {difficulty} | {row.get('count', 0)} | {row.get('correctness', 0):.4f} | "
            f"{row.get('relevance', 0):.4f} | {row.get('groundedness', 0):.4f} | "
            f"{row.get('conciseness', 0):.4f} |"
        )

    lines.extend(
        [
            "",
            "## Justification",
            "",
            "The selected configuration maximizes the weighted composite score while balancing answer correctness "
            "and groundedness. This weighting favors factually aligned, source-supported answers over merely "
            "question-matching outputs. Compare the easy/medium/hard rows above to verify whether the best setting "
            "wins consistently or only on one difficulty bucket.",
            "",
        ]
    )
    if best.get("langsmith_url"):
        lines.append(f"- LangSmith experiment URL: {best['langsmith_url']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-name", default="rag580-eval")
    parser.add_argument("--config-file")
    parser.add_argument(
        "--report-path",
        default=str(PROJECT_ROOT / "eval" / "langsmith_config_sweep_report.md"),
    )
    parser.add_argument("--skip-langsmith", action="store_true")
    args = parser.parse_args()

    configure_langsmith()
    items = load_eval_items()
    configs = load_configs(args.config_file)
    original_settings = deepcopy(get_settings())
    original_chroma_dir = app_settings.chroma_dir

    client: Client | None = None
    langsmith_enabled = bool(os.environ.get("LANGSMITH_API_KEY")) and not args.skip_langsmith
    if langsmith_enabled:
        client = Client()
        dataset = ensure_langsmith_dataset(client, args.dataset_name, items)
        dataset_examples = list(client.list_examples(dataset_id=dataset.id))
        if not dataset_examples:
            raise RuntimeError(
                f"LangSmith dataset '{args.dataset_name}' has no examples. "
                "Recreate the dataset or use a new dataset name."
            )
    else:
        dataset = None
        dataset_examples = None

    results: list[dict[str, Any]] = []
    try:
        for idx, config in enumerate(configs, 1):
            print(f"[{idx}/{len(configs)}] Running {format_config(config)}")
            update_settings(**config)
            sweep_chroma_dir = get_sweep_chroma_dir(config)
            sweep_chroma_dir.parent.mkdir(parents=True, exist_ok=True)
            app_settings.chroma_dir = sweep_chroma_dir
            vs_mod.invalidate_cache()
            if has_existing_index(sweep_chroma_dir):
                print(
                    f"[{idx}/{len(configs)}] indexing skipped | reusing existing index at {sweep_chroma_dir}",
                    flush=True,
                )
            else:
                if sweep_chroma_dir.exists():
                    shutil.rmtree(sweep_chroma_dir)
                progress_logger = make_progress_logger(idx, len(configs))
                ingest.index_all_pdfs(
                    progress_callback=progress_logger,
                    reset_store=True,
                )
                print(f"[{idx}/{len(configs)}] indexing 100% | completed", flush=True)

            langsmith_url = None
            if langsmith_enabled:
                experiment_results = evaluate(
                    predict,
                    data=dataset_examples,
                    evaluators=EVALUATORS,
                    experiment_prefix=(
                        "rag580-sweep-"
                        f"c{config['chunk_size']}-"
                        f"o{config['chunk_overlap']}-"
                        f"k{config['top_k']}"
                    ),
                    metadata={
                        "app": "rag580",
                        "dataset_items": len(items),
                        "chunk_size": config["chunk_size"],
                        "chunk_overlap": config["chunk_overlap"],
                        "top_k": config["top_k"],
                    },
                )
                experiment_name = getattr(experiment_results, "experiment_name", None)
                experiment_url = getattr(experiment_results, "url", None)
                langsmith_url = experiment_url or experiment_name

            records = run_local_eval(items)
            summary = summarize(records)
            composite_score = score_summary(summary)
            results.append(
                {
                    "config": deepcopy(config),
                    "summary": summary,
                    "composite_score": composite_score,
                    "langsmith_url": langsmith_url,
                }
            )
    finally:
        app_settings.chroma_dir = original_chroma_dir
        vs_mod.invalidate_cache()
        save_settings(original_settings)

    report = build_report(
        results,
        dataset_name=args.dataset_name,
        langsmith_enabled=langsmith_enabled,
    )
    Path(args.report_path).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
