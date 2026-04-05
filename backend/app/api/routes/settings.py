from pydantic import BaseModel, Field

from fastapi import APIRouter

from app.core import runtime_settings as rs

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsBody(BaseModel):
    chunk_size: int | None = Field(default=None, ge=100, le=8000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=256)
    llm_model: str | None = Field(default=None, min_length=1, max_length=256)


@router.get("")
def get_settings():
    s = rs.get_settings()
    return s.model_dump()


@router.put("")
def put_settings(body: SettingsBody):
    s = rs.update_settings(
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        top_k=body.top_k,
        embedding_model=body.embedding_model,
        llm_model=body.llm_model,
    )
    return s.model_dump()
