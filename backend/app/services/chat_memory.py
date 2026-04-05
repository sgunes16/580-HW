"""Conversation memory with ~50k-token budget and automatic compaction via summarization."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

# Total model context window (input-oriented budget before compaction).
CONTEXT_WINDOW_TOKENS = 50_000
# Reserve space for model output inside the same window.
OUTPUT_RESERVE_TOKENS = 8_192
# Prompt framing, system text, separators.
FORMAT_RESERVE_TOKENS = 2_000

# Rough heuristic: ~4 characters per token for English text.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def history_token_total(history: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(m.get("content", "")) for m in history)


def available_history_budget(
    *,
    context_tokens: int,
    question_tokens: int,
) -> int:
    """Tokens left for prior conversation after RAG context and current question."""
    used = (
        context_tokens
        + question_tokens
        + FORMAT_RESERVE_TOKENS
        + OUTPUT_RESERVE_TOKENS
    )
    return max(0, CONTEXT_WINDOW_TOKENS - used)


def build_context_usage(
    *,
    system_text: str,
    compacted_history: list[dict[str, str]],
    final_user_text: str,
    history_before: list[dict[str, str]],
    memory_compacted: bool,
) -> dict[str, Any]:
    """
    Estimated token usage for the next LLM call (rough heuristic: chars/4).
    """
    system_tokens = estimate_tokens(system_text)
    history_tokens = history_token_total(compacted_history)
    final_tokens = estimate_tokens(final_user_text)
    history_raw_tokens = history_token_total(history_before)

    estimated_input_tokens = system_tokens + history_tokens + final_tokens
    # Small overhead for message roles / chat template (approximate).
    overhead_tokens = max(50, estimated_input_tokens // 50)
    estimated_total = estimated_input_tokens + overhead_tokens

    window = CONTEXT_WINDOW_TOKENS
    pct_full = min(100.0, round(100.0 * estimated_total / window, 1))
    budget_after_output = max(1, window - OUTPUT_RESERVE_TOKENS)
    pct_input_budget = min(
        100.0, round(100.0 * estimated_total / budget_after_output, 1)
    )
    free_tokens = max(0, window - OUTPUT_RESERVE_TOKENS - estimated_total)

    parts = system_tokens + history_tokens + final_tokens
    seg = {
        "system": system_tokens,
        "history": history_tokens,
        "documents_and_question": final_tokens,
    }
    seg_pct = {
        k: (round(100.0 * v / parts, 1) if parts else 0.0) for k, v in seg.items()
    }

    return {
        "window_tokens": window,
        "reserved_output_tokens": OUTPUT_RESERVE_TOKENS,
        "reserved_format_tokens": FORMAT_RESERVE_TOKENS,
        "estimated_input_tokens": estimated_total,
        "estimated_overhead_tokens": overhead_tokens,
        "percent_of_window": pct_full,
        "percent_of_input_budget": pct_input_budget,
        "free_tokens_estimate": free_tokens,
        "breakdown": {
            **seg,
            "history_tokens_before_compact": history_raw_tokens,
            "segments_percent": seg_pct,
        },
        "memory_compacted": memory_compacted,
    }


def compact_history(
    history: list[dict[str, str]],
    budget_tokens: int,
    llm: ChatOllama,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """
    If history exceeds budget, summarize older turns with the same LLM, then keep recent turns.
    Returns (compacted_history, meta).
    """
    if not history:
        return [], {"compacted": False}

    if history_token_total(history) <= budget_tokens:
        return list(history), {"compacted": False}

    # Reserve roughly half the budget for recent raw turns; older turns are summarized.
    keep_budget = max(64, budget_tokens // 2)
    recent: list[dict[str, str]] = []
    seen = 0
    for m in reversed(history):
        t = estimate_tokens(m.get("content", ""))
        if seen + t > keep_budget and recent:
            break
        recent.append(m)
        seen += t
    recent.reverse()
    old = history[: len(history) - len(recent)]

    if not old:
        # Single huge message: hard-truncate
        h = dict(recent[0])
        max_chars = max(CHARS_PER_TOKEN * budget_tokens, 500)
        h["content"] = (h.get("content") or "")[:max_chars] + "\n[truncated]"
        return [h], {"compacted": True, "reason": "truncated_oversized_turn"}

    transcript = "\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in old
    )
    summarize_prompt = (
        "Summarize the following prior chat turns for a retrieval-augmented assistant. "
        "Preserve facts, definitions, user preferences, and open questions. "
        "Be concise (max ~600 words). Use bullet points if helpful.\n\n"
        f"{transcript}"
    )
    try:
        summary_msg = llm.invoke([HumanMessage(content=summarize_prompt)])
        summary = (
            summary_msg.content
            if hasattr(summary_msg, "content")
            else str(summary_msg)
        )
    except Exception as exc:
        logger.warning("Summarization failed, falling back to truncation: %s", exc)
        summary = transcript[: budget_tokens * CHARS_PER_TOKEN] + "\n[truncated]"

    summary_block = "[Earlier conversation summary]\n" + summary.strip()
    combined: list[dict[str, str]] = [
        {"role": "user", "content": summary_block},
    ] + list(recent)

    # Drop oldest recent turns until under budget; then truncate summary if needed.
    while history_token_total(combined) > budget_tokens and len(combined) > 2:
        combined.pop(1)

    if history_token_total(combined) > budget_tokens and combined:
        max_chars = max(400, budget_tokens * CHARS_PER_TOKEN - 50)
        combined[0]["content"] = (combined[0].get("content") or "")[:max_chars] + "\n[truncated]"

    meta: dict[str, Any] = {
        "compacted": True,
        "summarized_turns": len(old),
        "kept_turns": len(recent),
        "summary_tokens": estimate_tokens(summary),
    }
    return combined, meta
