from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.market_sentiment import market_sentiment_service
from ..services.ragflow_client import ragflow_client

router = APIRouter(prefix="/ragflow", tags=["ragflow"])


class RagflowChatIn(BaseModel):
    question: str = Field(min_length=1)
    chat_id: str | None = None
    model: str = "ragflow"
    include_reference: bool = True


class RagflowMarketDatasetIn(BaseModel):
    dataset_name: str = Field(default="cardflip_market_knowledge", min_length=1, max_length=128)
    chunk_method: str = Field(default="naive", min_length=1, max_length=32)


class RagflowUploadDocumentsIn(BaseModel):
    dataset_id: str | None = None
    dataset_name: str = Field(default="cardflip_market_knowledge", min_length=1, max_length=128)
    chunk_method: str = Field(default="naive", min_length=1, max_length=32)
    file_paths: list[str] = Field(default_factory=list, min_length=1)
    auto_parse: bool = True
    picture_chunk_for_images: bool = True


class RagflowMarketSentimentIn(BaseModel):
    title: str = Field(min_length=1)
    mode: str = Field(default="balanced")
    expected_sale_price: float = Field(gt=0)
    suggested_list_price: float = Field(gt=0)
    similar_sold_prices: list[float] = Field(default_factory=list)


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


@router.get("/datasets")
def ragflow_list_datasets(
    page: int = Query(default=1, ge=1, le=100),
    page_size: int = Query(default=50, ge=1, le=200),
    name: str = Query(default=""),
) -> dict[str, Any]:
    try:
        items = ragflow_client.list_datasets(page=page, page_size=page_size, name=name)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAGFlow request failed: {exc}") from exc
    return {"items": items, "count": len(items)}


@router.post("/datasets/ensure")
def ragflow_ensure_market_dataset(payload: RagflowMarketDatasetIn) -> dict[str, Any]:
    try:
        dataset = ragflow_client.ensure_market_dataset(
            dataset_name=payload.dataset_name,
            chunk_method=payload.chunk_method,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAGFlow request failed: {exc}") from exc
    return {"dataset": dataset}


@router.post("/datasets/upload-docs")
def ragflow_upload_documents(payload: RagflowUploadDocumentsIn) -> dict[str, Any]:
    try:
        dataset_id = (payload.dataset_id or "").strip()
        if not dataset_id:
            ensured = ragflow_client.ensure_market_dataset(
                dataset_name=payload.dataset_name,
                chunk_method=payload.chunk_method,
            )
            dataset_id = str(ensured.get("id") or "").strip()
            if not dataset_id:
                raise RuntimeError("failed to resolve dataset_id")

        docs = ragflow_client.upload_documents(
            dataset_id=dataset_id,
            file_paths=payload.file_paths,
        )
        image_ext = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tiff"}
        image_doc_ids: list[str] = []
        doc_ids: list[str] = []
        for row in docs:
            doc_id = str(row.get("id") or row.get("document_id") or "").strip()
            if not doc_id:
                continue
            doc_ids.append(doc_id)
            suffix = str(row.get("type") or "").strip().lower()
            name = str(row.get("name") or "").strip().lower()
            if suffix == "picture" or any(name.endswith(ext) for ext in image_ext):
                image_doc_ids.append(doc_id)

        if payload.picture_chunk_for_images:
            for doc_id in image_doc_ids:
                ragflow_client.update_document(
                    dataset_id=dataset_id,
                    document_id=doc_id,
                    chunk_method="picture",
                )

        if payload.auto_parse and doc_ids:
            ragflow_client.parse_documents(dataset_id=dataset_id, document_ids=doc_ids)

        return {
            "dataset_id": dataset_id,
            "uploaded": len(docs),
            "parsed": len(doc_ids) if payload.auto_parse else 0,
            "image_docs_reconfigured": len(image_doc_ids) if payload.picture_chunk_for_images else 0,
            "items": docs,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAGFlow request failed: {exc}") from exc


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


@router.post("/market-sentiment")
def ragflow_market_sentiment(payload: RagflowMarketSentimentIn) -> dict[str, Any]:
    try:
        return market_sentiment_service.assess_pricing_adjustment(
            title=payload.title,
            mode=payload.mode,
            expected_sale_price=payload.expected_sale_price,
            suggested_list_price=payload.suggested_list_price,
            similar_sold_prices=payload.similar_sold_prices,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAG sentiment failed: {exc}") from exc
