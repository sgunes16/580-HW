import json
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, Field, model_validator

from app.config import settings as app_settings


class RagRuntimeSettings(BaseModel):
    chunk_size: int = Field(ge=100, le=8000)
    chunk_overlap: int = Field(ge=0, le=2000)
    top_k: int = Field(ge=1, le=20)
    embedding_model: str = Field(min_length=1, max_length=256)
    llm_model: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def overlap_must_be_smaller_than_chunk(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self


_lock = Lock()
_cache: RagRuntimeSettings | None = None


def _defaults() -> RagRuntimeSettings:
    return RagRuntimeSettings(
        chunk_size=app_settings.default_chunk_size,
        chunk_overlap=app_settings.default_chunk_overlap,
        top_k=app_settings.default_top_k,
        embedding_model=app_settings.default_embedding_model,
        llm_model=app_settings.default_llm_model,
    )


def load_settings() -> RagRuntimeSettings:
    global _cache
    path: Path = app_settings.settings_file
    with _lock:
        if _cache is not None:
            return _cache
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            try:
                _cache = RagRuntimeSettings.model_validate(data)
            except Exception:
                _cache = _defaults()
                path.write_text(_cache.model_dump_json(indent=2), encoding="utf-8")
        else:
            _cache = _defaults()
            path.write_text(_cache.model_dump_json(indent=2), encoding="utf-8")
        return _cache


def save_settings(s: RagRuntimeSettings) -> RagRuntimeSettings:
    global _cache
    path: Path = app_settings.settings_file
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(s.model_dump_json(indent=2), encoding="utf-8")
        _cache = s
        return s


def get_settings() -> RagRuntimeSettings:
    return load_settings()


def update_settings(**kwargs) -> RagRuntimeSettings:
    current = load_settings().model_dump()
    current.update({k: v for k, v in kwargs.items() if v is not None})
    return save_settings(RagRuntimeSettings.model_validate(current))
