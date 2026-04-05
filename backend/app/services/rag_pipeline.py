from __future__ import annotations

from collections.abc import Iterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.config import settings as app_settings
from app.core.runtime_settings import get_settings
from app.services import chat_memory as mem
from app.services import vector_store as vs_mod

SYSTEM_PROMPT = """You are a retrieval-augmented assistant for course materials focused on software engineering,
data engineering, data systems, distributed systems, databases, machine learning systems,
data science, analytics, and practical software development.

Your job is to give answers that are useful to someone building, analyzing, or reasoning about
real software systems.

Behavior rules:
1. Treat the provided "Document excerpts" as the primary source of truth for the current answer.
2. Use prior conversation context only for continuity, not as a replacement for the retrieved excerpts.
3. If the excerpts are insufficient, say so briefly and naturally, without turning the answer into an evidence report.
4. Do not invent claims, definitions, numbers, quotations, or implementation details that are not supported.
5. If some part of the answer requires background knowledge beyond the excerpts, weave that in naturally and make the boundary clear in plain language.
6. Prefer precise, technically correct explanations over vague summaries.
7. When relevant, explain trade-offs, system design implications, performance considerations, failure modes, and implementation consequences.
8. When the user asks a practical question, connect the material to software usage such as architecture, APIs, storage, pipelines, testing, observability, deployment, scaling, reliability, data quality, experimentation, or model behavior.
9. Use concise structure when helpful: short paragraphs, bullets, or small step lists.
10. Respond in clear English.

Answer style:
- Be direct and technically grounded.
- Favor actionable explanations that would help a software engineer, data engineer, or data scientist.
- If the material contains competing approaches, compare them briefly and explain when each fits.
- If a concept is abstract, make it concrete with a small software-oriented example.
- If the user asks for code, algorithms, or implementation advice, stay consistent with the retrieved material and mention any important assumptions or limits.
- Do not use formulaic phrases like "According to the retrieved excerpts", "the book says", "in the context of the book", "supported by the excerpts", "not supported by the excerpts", or "general software engineering inference" unless the user explicitly asks for a source-analysis style answer.
- Do not mention the retrieval process, the excerpts, the source text, or the fact that the answer comes from a book unless the user explicitly asks about sources or grounding.
- Keep the answer natural and conversational, while still being precise and grounded."""

SYSTEM_PROMPT_NO_INDEX = """You are a helpful assistant for software engineering, data engineering,
data systems, and data science questions, but no document index is loaded yet.

Answer from general knowledge when appropriate, but clearly say that course-material grounding is not currently available.
Do not pretend that you are citing or using indexed documents when none are loaded.
Respond in clear English."""


def _history_dicts_to_messages(turns: list[dict[str, str]]) -> list[HumanMessage | AIMessage]:
    out: list[HumanMessage | AIMessage] = []
    for m in turns:
        role = (m.get("role") or "user").lower()
        content = m.get("content") or ""
        if role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def _chunk_text(chunk: object) -> str:
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text") or "")
        return "".join(parts)
    return str(content or "")


def _build_chat_state(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> dict:
    history = history or []
    for m in history:
        if m.get("role") not in ("user", "assistant"):
            raise ValueError("history items must have role 'user' or 'assistant'")

    rs = get_settings()
    vs = vs_mod.get_vectorstore()

    if vs is None:
        context = "(No documents indexed yet.)"
        sources: list[dict] = []
    else:
        retriever = vs.as_retriever(search_kwargs={"k": rs.top_k})
        docs = retriever.invoke(question)
        context_parts = []
        sources = []
        for i, d in enumerate(docs):
            context_parts.append(d.page_content)
            meta = d.metadata or {}
            sources.append(
                {
                    "rank": i + 1,
                    "source": meta.get("source", "unknown"),
                    "page": meta.get("page"),
                    "snippet": (d.page_content[:400] + "…")
                    if len(d.page_content) > 400
                    else d.page_content,
                }
            )
        context = (
            "\n\n---\n\n".join(context_parts) if context_parts else "(empty retrieval)"
        )

    context_tokens = mem.estimate_tokens(context)
    question_tokens = mem.estimate_tokens(question)
    budget = mem.available_history_budget(
        context_tokens=context_tokens,
        question_tokens=question_tokens,
    )

    llm = ChatOllama(
        model=rs.llm_model,
        base_url=app_settings.ollama_base_url,
        temperature=0.2,
    )
    summarizer = ChatOllama(
        model=rs.llm_model,
        base_url=app_settings.ollama_base_url,
        temperature=0.1,
    )

    memory_meta: dict = {"compacted": False}
    compacted_history: list[dict[str, str]] = []
    if history:
        effective_budget = max(256, budget) if budget > 0 else 512
        compacted_history, mem_meta = mem.compact_history(
            history, effective_budget, summarizer
        )
        memory_meta.update(mem_meta)

    system_text = SYSTEM_PROMPT_NO_INDEX if vs is None else SYSTEM_PROMPT
    messages: list = [SystemMessage(content=system_text)]
    messages.extend(_history_dicts_to_messages(compacted_history))
    final_user = (
        "Use the material below to answer the user's question.\n"
        "Write the answer naturally and directly.\n"
        "Do not mention books, excerpts, retrieval, source text, or grounding unless the user asks for that.\n\n"
        f"Material:\n{context}\n\n"
        f"Question:\n{question}"
    )
    messages.append(HumanMessage(content=final_user))

    context_usage = mem.build_context_usage(
        system_text=system_text,
        compacted_history=compacted_history,
        final_user_text=final_user,
        history_before=history,
        memory_compacted=bool(memory_meta.get("compacted")),
    )

    return {
        "llm": llm,
        "messages": messages,
        "sources": sources,
        "memory": memory_meta,
        "context_usage": context_usage,
    }


def answer_question(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> dict:
    state = _build_chat_state(question, history=history)
    result = state["llm"].invoke(state["messages"])
    text = result.content if hasattr(result, "content") else str(result)

    out: dict = {
        "answer": text,
        "sources": state["sources"],
        "memory": state["memory"],
        "context_usage": state["context_usage"],
    }
    return out


def stream_answer(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> tuple[Iterator[str], dict]:
    state = _build_chat_state(question, history=history)

    def gen() -> Iterator[str]:
        for chunk in state["llm"].stream(state["messages"]):
            text = _chunk_text(chunk)
            if text:
                yield text

    meta = {
        "sources": state["sources"],
        "memory": state["memory"],
        "context_usage": state["context_usage"],
    }
    return gen(), meta
