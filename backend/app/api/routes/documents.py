from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import settings as app_settings
from app.services import ingest
from app.services.reindex_jobs import get_job, start_reindex_job

router = APIRouter(prefix="/documents", tags=["documents"])


class ReindexRequest(BaseModel):
    """Index one PDF by basename, or omit filename to index all PDFs in data/pdfs."""

    filename: str | None = Field(
        default=None,
        description="Basename only, e.g. myfile.pdf. Omit to index every PDF.",
    )
    reset: bool = Field(
        default=False,
        description="If true, delete the entire Chroma store before indexing (full rebuild).",
    )


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    app_settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    dest = app_settings.pdf_dir / safe_name

    content = await file.read()
    dest.write_bytes(content)

    return {"filename": safe_name, "path": str(dest), "bytes": len(content)}


@router.get("/list")
def list_pdfs():
    return ingest.list_pdf_index_statuses()


@router.get("/reindex/jobs/{job_id}")
def reindex_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/reindex")
def reindex_start(body: ReindexRequest | None = None):
    """Start a background indexing job. Poll GET /reindex/jobs/{job_id} for progress."""
    body = body or ReindexRequest()
    filename: str | None = None
    if body.filename is not None:
        try:
            filename = ingest._safe_pdf_name(body.filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        pdf_path = app_settings.pdf_dir / filename
        if not pdf_path.is_file():
            raise HTTPException(status_code=404, detail=f"PDF not found: {filename}")

    job_id = start_reindex_job(filename, reset_store=body.reset)
    return {"job_id": job_id, "status": "queued"}


@router.delete("/index/{filename}")
def delete_pdf_index(filename: str):
    try:
        safe = ingest._safe_pdf_name(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = ingest.delete_index_for_pdf(safe)
    if not result["deleted"]:
        raise HTTPException(status_code=404, detail=f"No index found for: {safe}")
    return result


@router.delete("/index")
def delete_all_indexes():
    return ingest.delete_all_indexes()
