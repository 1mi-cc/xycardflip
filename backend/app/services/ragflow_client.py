from __future__ import annotations

from typing import Any

import requests

from ..config import settings
from .proxy_resolver import request_get
from .proxy_resolver import request_post
from .proxy_resolver import resolve_proxy_for_url


class RagflowClient:
    def __init__(self) -> None:
        self.base_url = str(settings.ragflow_base_url or "").strip().rstrip("/")
        self.api_key = str(settings.ragflow_api_key or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(settings.ragflow_enabled)

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def status(self) -> dict[str, Any]:
        status = {
            "enabled": self.enabled,
            "configured": self.configured,
            "base_url": self.base_url,
            "chat_id_configured": bool(str(settings.ragflow_chat_id or "").strip()),
            "api_key_configured": bool(self.api_key),
            "reachable": False,
        }
        if not self.enabled:
            status["message"] = "RAGFlow disabled (RAGFLOW_ENABLED=false)."
            return status
        if not self.configured:
            status["message"] = "RAGFlow config missing. Set RAGFLOW_BASE_URL and RAGFLOW_API_KEY."
            return status
        try:
            chats = self.list_chats(page=1, page_size=1)
            status["reachable"] = True
            status["sample_chat_count"] = len(chats)
            status["message"] = "ok"
        except Exception as exc:
            status["message"] = str(exc)
        return status

    def list_chats(self, *, page: int = 1, page_size: int = 30) -> list[dict[str, Any]]:
        payload = self._request_json(
            "GET",
            "/api/v1/chats",
            params={"page": page, "page_size": page_size, "desc": True, "orderby": "update_time"},
        )
        if payload.get("code") != 0:
            raise RuntimeError(f"RAGFlow list chats failed: {payload.get('message') or 'unknown'}")
        data = payload.get("data") or []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def create_chat_completion(
        self,
        *,
        question: str,
        chat_id: str | None = None,
        model: str = "ragflow",
        include_reference: bool = True,
    ) -> dict[str, Any]:
        self._ensure_ready()
        selected_chat_id = (chat_id or settings.ragflow_chat_id or "").strip()
        if not selected_chat_id:
            raise RuntimeError("Missing chat_id. Set RAGFLOW_CHAT_ID or pass chat_id in request.")
        if not str(question or "").strip():
            raise RuntimeError("question cannot be empty")

        payload = self._request_json(
            "POST",
            f"/api/v1/chats_openai/{selected_chat_id}/chat/completions",
            json={
                "model": model or "ragflow",
                "messages": [{"role": "user", "content": question}],
                "stream": False,
                "extra_body": {"reference": bool(include_reference)},
            },
        )

        if "code" in payload and payload.get("code") not in (None, 0):
            raise RuntimeError(f"RAGFlow chat failed: {payload.get('message') or 'unknown'}")

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("RAGFlow returned no choices")

        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        answer = str(message.get("content") or "").strip()
        if not answer:
            raise RuntimeError("RAGFlow returned empty answer")

        return {
            "chat_id": selected_chat_id,
            "answer": answer,
            "reference": message.get("reference") if include_reference else None,
            "raw": payload,
        }

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_ready()
        url = f"{self.base_url}{path}"
        proxies = resolve_proxy_for_url(url)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = float(settings.ragflow_timeout_sec or 45.0)
        try:
            if method.upper() == "GET":
                resp = request_get(
                    url,
                    headers=headers,
                    params=params or {},
                    timeout=timeout,
                    proxies=proxies,
                )
            else:
                resp = request_post(
                    url,
                    headers=headers,
                    params=params or {},
                    json=json or {},
                    timeout=timeout,
                    proxies=proxies,
                )
        except requests.RequestException as exc:
            raise RuntimeError(f"RAGFlow request error: {exc}") from exc

        if resp.status_code >= 400:
            excerpt = (resp.text or "")[:240]
            raise RuntimeError(f"RAGFlow HTTP {resp.status_code}: {excerpt}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise RuntimeError("RAGFlow returned non-JSON response") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("RAGFlow returned unsupported JSON payload")
        return payload

    def _ensure_ready(self) -> None:
        if not self.enabled:
            raise RuntimeError("RAGFlow is disabled. Set RAGFLOW_ENABLED=true.")
        if not self.base_url:
            raise RuntimeError("RAGFLOW_BASE_URL is empty.")
        if not self.api_key:
            raise RuntimeError("RAGFLOW_API_KEY is empty.")


ragflow_client = RagflowClient()
