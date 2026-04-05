from fastapi import APIRouter, HTTPException

from app.db import chat_db

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("")
def list_chats():
    return {"conversations": chat_db.list_conversations()}


@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: str):
    if not chat_db.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": conversation_id,
        "messages": chat_db.get_messages(conversation_id),
    }


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str):
    if not chat_db.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True, "id": conversation_id}
