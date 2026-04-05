import json
from typing import Literal

from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.http_utils import raise_from_service_error
from app.db import chat_db
from app.services import rag_pipeline

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=32000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    history: list[ChatTurn] = Field(
        default_factory=list,
        max_length=200,
        description="Prior turns only (not including the current question).",
    )
    conversation_id: str | None = Field(
        default=None,
        max_length=36,
        description="Existing SQLite conversation id, or omit to start a new one.",
    )


@router.post("")
def chat(req: ChatRequest):
    try:
        if req.conversation_id and not chat_db.conversation_exists(req.conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")

        history = [t.model_dump() for t in req.history]
        out = rag_pipeline.answer_question(
            req.question.strip(),
            history=history,
        )

        if req.conversation_id:
            conv_id = req.conversation_id
        else:
            title = (req.question.strip()[:120] or "New chat").replace("\n", " ")
            conv_id = chat_db.create_conversation(title=title)

        chat_db.add_message(conv_id, "user", req.question.strip())
        chat_db.add_message(conv_id, "assistant", out.get("answer") or "")
        chat_db.touch_conversation(conv_id)

        out["conversation_id"] = conv_id
        return out
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise_from_service_error(exc)


@router.post("/stream")
def chat_stream(req: ChatRequest):
    try:
        if req.conversation_id and not chat_db.conversation_exists(req.conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")

        history = [t.model_dump() for t in req.history]
        if req.conversation_id:
            conv_id = req.conversation_id
        else:
            title = (req.question.strip()[:120] or "New chat").replace("\n", " ")
            conv_id = chat_db.create_conversation(title=title)

        stream_iter, meta = rag_pipeline.stream_answer(
            req.question.strip(),
            history=history,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise_from_service_error(exc)

    def encode(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False) + "\n"

    def event_stream():
        parts: list[str] = []
        yield encode({"type": "start", "conversation_id": conv_id})
        try:
            for text in stream_iter:
                parts.append(text)
                yield encode({"type": "delta", "delta": text})

            answer = "".join(parts)
            chat_db.add_message(conv_id, "user", req.question.strip())
            chat_db.add_message(conv_id, "assistant", answer)
            chat_db.touch_conversation(conv_id)

            yield encode(
                {
                    "type": "done",
                    "conversation_id": conv_id,
                    "answer": answer,
                    "sources": meta.get("sources") or [],
                    "memory": meta.get("memory"),
                    "context_usage": meta.get("context_usage"),
                }
            )
        except Exception as exc:
            yield encode({"type": "error", "error": str(exc)})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
