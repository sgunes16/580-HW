from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings as app_settings
from app.core.runtime_settings import get_settings
from app.services import vector_store as vs_mod

logger = logging.getLogger(__name__)

ProgressFn = Callable[[float, str], None]

EMBED_BATCH_SIZE = 32


def _safe_pdf_name(name: str) -> str:
    if not name or not str(name).strip():
        raise ValueError("filename is required")
    name = str(name).strip()
    p = Path(name)
    if p.name != name:
        raise ValueError("filename must be a basename only (no path)")
    if ".." in name:
        raise ValueError("invalid filename")
    if p.suffix.lower() != ".pdf":
        raise ValueError("only .pdf files are allowed")
    return p.name


def load_pdf_documents(pdf_paths: list[Path]) -> list:
    docs = []
    for p in pdf_paths:
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue
        loader = PyPDFLoader(str(p))
        for d in loader.load():
            d.metadata.setdefault("source", p.name)
            docs.append(d)
    return docs


def _open_vectorstore() -> Chroma:
    app_settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    embeddings = vs_mod.build_embeddings()
    vs_mod.invalidate_cache()
    return Chroma(
        persist_directory=str(app_settings.chroma_dir),
        embedding_function=embeddings,
        collection_name="course_rag",
    )


def _remove_chunks_for_source(vs: Chroma, source_name: str) -> None:
    try:
        vs.delete(where={"source": source_name})
    except Exception as e:
        logger.info("delete where source=%s: %s (may be first index)", source_name, e)


def _collect_index_stats() -> dict[str, dict]:
    vs = vs_mod.get_vectorstore()
    if vs is None:
        return {}

    try:
        rows = vs.get(include=["metadatas"])
    except Exception as exc:
        logger.warning("Could not inspect vector store metadata: %s", exc)
        return {}

    metadatas = rows.get("metadatas") or []
    stats: dict[str, dict] = {}
    for meta in metadatas:
        if not isinstance(meta, dict):
            continue
        source = meta.get("source")
        if not source:
            continue
        item = stats.setdefault(
            source,
            {
                "source": source,
                "chunk_count": 0,
                "last_indexed_at": None,
            },
        )
        item["chunk_count"] += 1
        indexed_at = meta.get("indexed_at")
        if indexed_at and (
            item["last_indexed_at"] is None or str(indexed_at) > str(item["last_indexed_at"])
        ):
            item["last_indexed_at"] = indexed_at
    return stats


def list_pdf_index_statuses() -> dict:
    app_settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p.name for p in app_settings.pdf_dir.glob("*.pdf"))
    stats = _collect_index_stats()

    documents = []
    for name in files:
        stat = stats.get(name) or {}
        chunk_count = int(stat.get("chunk_count") or 0)
        documents.append(
            {
                "filename": name,
                "is_indexed": chunk_count > 0,
                "chunk_count": chunk_count,
                "last_indexed_at": stat.get("last_indexed_at"),
            }
        )

    orphaned_indexes = [
        {
            "filename": source,
            "chunk_count": int(stat.get("chunk_count") or 0),
            "last_indexed_at": stat.get("last_indexed_at"),
        }
        for source, stat in sorted(stats.items())
        if source not in files
    ]

    indexed_documents = sum(1 for doc in documents if doc["is_indexed"])
    indexed_chunks = sum(doc["chunk_count"] for doc in documents)
    orphaned_chunks = sum(item["chunk_count"] for item in orphaned_indexes)

    return {
        "files": files,
        "count": len(files),
        "documents": documents,
        "indexed_summary": {
            "pdf_count": len(files),
            "indexed_pdf_count": indexed_documents,
            "indexed_chunk_count": indexed_chunks,
            "orphaned_index_count": len(orphaned_indexes),
            "orphaned_chunk_count": orphaned_chunks,
        },
        "orphaned_indexes": orphaned_indexes,
    }


def delete_index_for_pdf(filename: str) -> dict:
    safe = _safe_pdf_name(filename)
    stats = _collect_index_stats()
    before = stats.get(safe)
    if not before:
        return {"filename": safe, "deleted_chunks": 0, "deleted": False}

    vs = _open_vectorstore()
    _remove_chunks_for_source(vs, safe)
    vs_mod.set_vectorstore(vs)
    return {
        "filename": safe,
        "deleted_chunks": int(before.get("chunk_count") or 0),
        "deleted": True,
    }


def delete_all_indexes() -> dict:
    stats = _collect_index_stats()
    total_sources = len(stats)
    total_chunks = sum(int(item.get("chunk_count") or 0) for item in stats.values())

    if app_settings.chroma_dir.exists():
        shutil.rmtree(app_settings.chroma_dir)
    vs_mod.invalidate_cache()

    return {
        "deleted": True,
        "deleted_sources": total_sources,
        "deleted_chunks": total_chunks,
    }


def index_one_pdf(filename: str, progress_callback: ProgressFn | None = None) -> dict:
    """Index a single PDF: remove old chunks for that file, then embed new chunks."""
    safe = _safe_pdf_name(filename)
    pdf_path = app_settings.pdf_dir / safe
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {safe}")

    def prog(pct: float, msg: str) -> None:
        if progress_callback:
            progress_callback(max(0.0, min(100.0, pct)), msg)

    rs = get_settings()
    prog(2, f"Loading {safe}…")
    documents = load_pdf_documents([pdf_path])
    if not documents:
        raise RuntimeError(f"Could not read PDF content: {safe}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=rs.chunk_size,
        chunk_overlap=rs.chunk_overlap,
    )
    prog(12, f"Splitting {safe}…")
    chunks = splitter.split_documents(documents)
    if not chunks:
        raise RuntimeError(f"No text chunks produced for: {safe}")

    indexed_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for i, chunk in enumerate(chunks):
        chunk.metadata["source"] = safe
        chunk.metadata["chunk_index"] = i
        chunk.metadata["indexed_at"] = indexed_at

    prog(22, f"Opening vector store…")
    vs = _open_vectorstore()
    prog(28, f"Removing old vectors for {safe}…")
    _remove_chunks_for_source(vs, safe)

    n = len(chunks)
    prog(35, f"Embedding {n} chunks for {safe}…")
    for start in range(0, n, EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vs.add_documents(batch)
        done = min(start + len(batch), n)
        sub = 35 + (done / n) * 65
        prog(sub, f"Embedding {safe}: {done}/{n} chunks")

    vs_mod.set_vectorstore(vs)
    prog(100, f"Finished {safe}")
    return {
        "indexed": 1,
        "chunks": n,
        "files": [safe],
    }


def index_all_pdfs(
    progress_callback: ProgressFn | None = None,
    *,
    reset_store: bool = False,
) -> dict:
    """Index every PDF in data/pdfs. Optionally wipe Chroma first (full rebuild)."""
    pdf_dir: Path = app_settings.pdf_dir
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        return {"indexed": 0, "chunks": 0, "message": "No PDF files in the data folder."}

    if reset_store and app_settings.chroma_dir.exists():
        if progress_callback:
            progress_callback(1, "Removing existing index (full reset)…")
        shutil.rmtree(app_settings.chroma_dir)
        vs_mod.invalidate_cache()

    total_files = len(pdfs)
    all_chunks = 0
    names: list[str] = []

    for i, path in enumerate(pdfs):
        base = (i / total_files) * 100
        span = 100 / total_files

        def inner(pct: float, msg: str, _base=base, _span=span) -> None:
            if progress_callback:
                overall = _base + (pct / 100.0) * _span
                progress_callback(overall, msg)

        r = index_one_pdf(path.name, progress_callback=inner)
        all_chunks += r["chunks"]
        names.extend(r.get("files", []))

    return {
        "indexed": total_files,
        "chunks": all_chunks,
        "files": names,
    }
