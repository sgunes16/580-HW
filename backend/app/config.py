from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_PROJECT_ROOT / ".env"),
            str(_BACKEND_ROOT / ".env"),
        ),
        extra="ignore",
    )

    project_root: Path = Path(__file__).resolve().parents[2]
    pdf_dir: Path = project_root / "data" / "pdfs"
    chroma_dir: Path = project_root / "data" / "chroma"
    settings_file: Path = project_root / "data" / "runtime_settings.json"
    database_path: Path = project_root / "data" / "app.db"

    ollama_base_url: str = "http://127.0.0.1:11434"
    default_embedding_model: str = "nomic-embed-text"
    default_llm_model: str = "llama3.2"
    default_chunk_size: int = 1000
    default_chunk_overlap: int = 150
    default_top_k: int = 4
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_endpoint: str | None = None
    langsmith_project: str = "rag580"
    langsmith_workspace_id: str | None = None

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost",
        "http://127.0.0.1",
    ]


settings = Settings()
