import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, chats, documents, settings
from app.config import settings as app_settings
from app.core.langsmith_setup import configure_langsmith
from app.db import chat_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_langsmith()
    chat_db.init_db()
    yield


app = FastAPI(title="Course RAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
