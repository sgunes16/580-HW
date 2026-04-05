from __future__ import annotations

from threading import Lock

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

from app.config import settings as app_settings
from app.core.runtime_settings import get_settings

_vectorstore: Chroma | None = None
_lock = Lock()
_collection_name = "course_rag"


def build_embeddings() -> OllamaEmbeddings:
    rs = get_settings()
    return OllamaEmbeddings(
        model=rs.embedding_model,
        base_url=app_settings.ollama_base_url,
    )


def get_vectorstore() -> Chroma | None:
    global _vectorstore
    with _lock:
        if _vectorstore is not None:
            return _vectorstore
        if not app_settings.chroma_dir.exists():
            return None
        try:
            _vectorstore = Chroma(
                persist_directory=str(app_settings.chroma_dir),
                embedding_function=build_embeddings(),
                collection_name=_collection_name,
            )
        except Exception:
            return None
        return _vectorstore


def invalidate_cache() -> None:
    global _vectorstore
    with _lock:
        _vectorstore = None


def set_vectorstore(vs: Chroma) -> None:
    global _vectorstore
    with _lock:
        _vectorstore = vs
