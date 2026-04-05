"""Shared helpers for API error responses."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.config import settings as app_settings

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None


def raise_from_service_error(exc: BaseException) -> None:
    """Map common RAG / Ollama failures to HTTP errors with clear messages."""
    msg_lower = str(exc).lower()
    if isinstance(exc, ConnectionError):
        logger.warning("Ollama connection error: %s", exc)
        _raise_ollama_unreachable()
    if httpx is not None and isinstance(
        exc,
        (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException),
    ):
        logger.warning("HTTP client error (likely Ollama): %s", exc)
        _raise_ollama_unreachable()
    if "failed to connect" in msg_lower or "connection refused" in msg_lower:
        logger.warning("Connection failure: %s", exc)
        _raise_ollama_unreachable()
    if "name or service not known" in msg_lower:
        logger.warning("DNS / host not known: %s", exc)
        _raise_ollama_unreachable()
    if "connection reset" in msg_lower:
        logger.warning("Connection reset: %s", exc)
        _raise_ollama_unreachable()
    logger.exception("Service error (returning 500): %s", exc)
    raise HTTPException(status_code=500, detail=str(exc)) from exc


def _raise_ollama_unreachable() -> None:
    raise HTTPException(
        status_code=503,
        detail=(
            f"Cannot reach Ollama at {app_settings.ollama_base_url}. "
            "Start the Ollama app on this machine, then run "
            "`ollama pull <your_embedding_model>` (see Settings). "
            "Docker: set OLLAMA_BASE_URL to http://host.docker.internal:11434 "
            "and ensure Ollama listens on 0.0.0.0:11434 if needed."
        ),
    )
