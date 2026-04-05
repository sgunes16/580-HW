from __future__ import annotations

import logging
import os

from app.config import settings as app_settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Mirror optional app settings into LangSmith env vars for LangChain tracing."""
    if not app_settings.langsmith_tracing:
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", app_settings.langsmith_project)

    if app_settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = app_settings.langsmith_api_key
    if app_settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = app_settings.langsmith_endpoint
    if app_settings.langsmith_workspace_id:
        os.environ["LANGSMITH_WORKSPACE_ID"] = app_settings.langsmith_workspace_id

    if not os.environ.get("LANGSMITH_API_KEY"):
        logger.warning(
            "LangSmith tracing enabled but LANGSMITH_API_KEY is missing; traces will not upload."
        )
    else:
        logger.info(
            "LangSmith tracing enabled for project '%s'.",
            os.environ.get("LANGSMITH_PROJECT", app_settings.langsmith_project),
        )
