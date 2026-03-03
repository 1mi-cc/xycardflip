from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.ragflow_client import ragflow_client

router = APIRouter(prefix="/ragflow", tags=["ragflow"])


class RagflowChatIn(BaseModel):
    question: str = Field(min_length=1)
    chat_id: str | None = None
    model: str = "ragflow"
    include_reference: bool = True


@router.get("/status")
def ragflow_status() -> dict[str, Any]:
    return ragflow_client.status()


@router.get("/chats")
def ragflow_list_chats(
    page: int = Query(default=1, ge=1, le=100),
    page_size: int = Query(default=30, ge=1, le=200),
) -> dict[str, Any]:
    try:
        items = ragflow_client.list_chats(page=page, page_size=page_size)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAGFlow request failed: {exc}") from exc
    return {"items": items, "count": len(items)}


@router.post("/chat")
def ragflow_chat(payload: RagflowChatIn) -> dict[str, Any]:
    try:
        return ragflow_client.create_chat_completion(
            question=payload.question,
            chat_id=payload.chat_id,
            model=payload.model,
            include_reference=payload.include_reference,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAGFlow request failed: {exc}") from exc
