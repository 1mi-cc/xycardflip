from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from .. import repositories as repo
from ..config import settings
from ..errors import BusyStateError
from .proxy_resolver import BusinessBanError
from .proxy_resolver import mark_proxy_bad
from .proxy_resolver import proxy_url_from_mapping
from .proxy_resolver import request_post
from .proxy_resolver import rotate_proxy
from .proxy_resolver import resolve_proxy_for_url


class ExecutionService:
    """Execution adapter for buy/list/sell actions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._retry_lock = threading.Lock()
        self._provider = (settings.execution_provider.strip().lower() or "disabled")
        self._live_enabled = bool(settings.execution_live_enabled)
        self._live_confirm_token = settings.execution_live_confirm_token.strip()
        self._live_confirm_required = bool(self._live_confirm_token)
        self._live_max_buy_price = max(0.0, float(settings.execution_live_max_buy_price))
        self._live_min_list_profit_ratio = max(
            0.0,
            float(settings.execution_live_min_list_profit_ratio),
        )
        self._live_min_sell_profit_ratio = max(
            0.0,
            float(settings.execution_live_min_sell_profit_ratio),
        )
        self._retry_last_busy_at = ""
        self._retry_last_busy_reason = ""

    def _runtime_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "provider": self._provider,
                "live_enabled": self._live_enabled,
                "live_confirm_required": self._live_confirm_required,
                "live_confirm_token": self._live_confirm_token,
                "live_max_buy_price": self._live_max_buy_price,
                "live_min_list_profit_ratio": self._live_min_list_profit_ratio,
                "live_min_sell_profit_ratio": self._live_min_sell_profit_ratio,
            }

    def update_config(
        self,
        *,
        provider: str | None = None,
        live_enabled: bool | None = None,
        live_confirm_required: bool | None = None,
        live_max_buy_price: float | None = None,
        live_min_list_profit_ratio: float | None = None,
        live_min_sell_profit_ratio: float | None = None,
    ) -> dict[str, Any]:
        valid_providers = {"mock", "webhook", "disabled", "none"}
        with self._lock:
            if provider is not None:
                normalized = str(provider).strip().lower()
                if normalized not in valid_providers:
                    raise ValueError("provider must be one of mock/webhook/disabled/none")
                self._provider = normalized
            if live_enabled is not None:
                self._live_enabled = bool(live_enabled)
            if live_confirm_required is not None:
                self._live_confirm_required = bool(live_confirm_required)
            if live_max_buy_price is not None:
                self._live_max_buy_price = max(0.0, min(1_000_000.0, float(live_max_buy_price)))
            if live_min_list_profit_ratio is not None:
                self._live_min_list_profit_ratio = max(
                    0.0,
                    min(10.0, float(live_min_list_profit_ratio)),
                )
            if live_min_sell_profit_ratio is not None:
                self._live_min_sell_profit_ratio = max(
                    0.0,
                    min(10.0, float(live_min_sell_profit_ratio)),
                )
        return self.status()

    def status(self) -> dict[str, Any]:
        runtime = self._runtime_snapshot()
        return {
            "provider": runtime["provider"],
            "timeout_sec": settings.execution_timeout_sec,
            "webhook_secret_configured": bool(settings.execution_webhook_secret.strip()),
            "webhook_max_retries": settings.execution_webhook_max_retries,
            "webhook_retry_backoff_sec": settings.execution_webhook_retry_backoff_sec,
            "webhook_buy_configured": bool(settings.execution_webhook_buy_url.strip()),
            "webhook_list_configured": bool(settings.execution_webhook_list_url.strip()),
            "webhook_sell_configured": bool(settings.execution_webhook_sell_url.strip()),
            "live_enabled": runtime["live_enabled"],
            "live_confirm_required": runtime["live_confirm_required"],
            "live_max_buy_price": runtime["live_max_buy_price"],
            "live_min_list_profit_ratio": runtime["live_min_list_profit_ratio"],
            "live_min_sell_profit_ratio": runtime["live_min_sell_profit_ratio"],
            "retry_failed_busy": self._retry_lock.locked(),
            "retry_failed_last_busy_at": self._retry_last_busy_at,
            "retry_failed_last_busy_reason": self._retry_last_busy_reason,
        }

    def retry_guard_status(self) -> dict[str, Any]:
        return {
            "service": "execution_retry_replay",
            "busy": self._retry_lock.locked(),
            "last_busy_at": self._retry_last_busy_at,
            "last_busy_reason": self._retry_last_busy_reason,
        }

    def _mark_retry_busy(self, reason: str) -> None:
        self._retry_last_busy_at = datetime.now(timezone.utc).isoformat()
        self._retry_last_busy_reason = reason

    def execute_list(
        self,
        trade_id: int,
        dry_run: bool = True,
        force: bool = False,
        confirm_token: str | None = None,
        listing_url: str = "",
        note: str = "",
        update_trade_state: bool = True,
    ) -> dict[str, Any]:
        trade = self._require_trade(trade_id)
        runtime = self._runtime_snapshot()
        provider = str(runtime["provider"])
        payload = {
            "action": "list",
            "trade_id": int(trade["id"]),
            "opportunity_id": int(trade["opportunity_id"]),
            "listing_row_id": int(trade["listing_row_id"]),
            "title": str(trade["title"]),
            "buy_price": float(trade["approved_buy_price"]),
            "target_sell_price": float(trade["target_sell_price"]),
            "status": str(trade["status"]),
            "requested_listing_url": str(listing_url or "").strip(),
        }
        guard_error = None
        if not dry_run:
            guard_error = self._validate_live_action_guard(
                action="list",
                trade=trade,
                provider=provider,
                force=force,
                confirm_token=confirm_token,
                payload=payload,
                runtime=runtime,
            )

        def _on_success_update(response_payload: dict[str, Any], external_id: str) -> dict[str, Any]:
            if not update_trade_state:
                return {"applied": False, "reason": "update_trade_state=false"}
            final_listing_url = self._resolve_listing_url(
                explicit_listing_url=listing_url,
                response_payload=response_payload,
                external_id=external_id,
                provider=provider,
                trade=trade,
            )
            update_note = note.strip() or f"execution list via {provider}"
            repo.update_trade_listed(trade_id, final_listing_url, update_note)
            return {
                "applied": True,
                "status": "listed_for_sale",
                "listing_url": final_listing_url,
            }

        return self._execute_action(
            trade_id=trade_id,
            action="list",
            provider=provider,
            payload=payload,
            dry_run=dry_run,
            force=force,
            webhook_url=settings.execution_webhook_list_url.strip(),
            guard_error=guard_error,
            on_success_update=_on_success_update,
        )

    def execute_sell(
        self,
        trade_id: int,
        dry_run: bool = True,
        force: bool = False,
        confirm_token: str | None = None,
        sold_price: float | None = None,
        note: str = "",
        update_trade_state: bool = True,
    ) -> dict[str, Any]:
        trade = self._require_trade(trade_id)
        runtime = self._runtime_snapshot()
        provider = str(runtime["provider"])
        if sold_price is not None and sold_price <= 0:
            raise ValueError("sold_price must be > 0")
        payload = {
            "action": "sell",
            "trade_id": int(trade["id"]),
            "opportunity_id": int(trade["opportunity_id"]),
            "listing_row_id": int(trade["listing_row_id"]),
            "title": str(trade["title"]),
            "buy_price": float(trade["approved_buy_price"]),
            "target_sell_price": float(trade["target_sell_price"]),
            "status": str(trade["status"]),
            "requested_sold_price": float(sold_price) if sold_price is not None else None,
        }
        guard_error = None
        if not dry_run:
            guard_error = self._validate_live_action_guard(
                action="sell",
                trade=trade,
                provider=provider,
                force=force,
                confirm_token=confirm_token,
                payload=payload,
                runtime=runtime,
            )

        def _on_success_update(response_payload: dict[str, Any], external_id: str) -> dict[str, Any]:
            if not update_trade_state:
                return {"applied": False, "reason": "update_trade_state=false"}
            final_sold_price = self._resolve_sold_price(
                requested_sold_price=sold_price,
                response_payload=response_payload,
                trade=trade,
            )
            update_note = note.strip() or f"execution sell via {provider}"
            if external_id:
                update_note = f"{update_note}; external_id={external_id}"
            repo.update_trade_sold(trade_id, final_sold_price, update_note)
            return {
                "applied": True,
                "status": "sold",
                "sold_price": final_sold_price,
            }

        return self._execute_action(
            trade_id=trade_id,
            action="sell",
            provider=provider,
            payload=payload,
            dry_run=dry_run,
            force=force,
            webhook_url=settings.execution_webhook_sell_url.strip(),
            guard_error=guard_error,
            on_success_update=_on_success_update,
        )

    def execute_buy(
        self,
        trade_id: int,
        dry_run: bool = True,
        force: bool = False,
        confirm_token: str | None = None,
    ) -> dict[str, Any]:
        trade = self._require_trade(trade_id)
        runtime = self._runtime_snapshot()
        provider = str(runtime["provider"])
        payload = {
            "action": "buy",
            "trade_id": int(trade["id"]),
            "opportunity_id": int(trade["opportunity_id"]),
            "listing_row_id": int(trade["listing_row_id"]),
            "title": str(trade["title"]),
            "buy_price": float(trade["approved_buy_price"]),
            "target_sell_price": float(trade["target_sell_price"]),
            "status": str(trade["status"]),
        }
        guard_error = None
        if not dry_run:
            guard_error = self._validate_live_action_guard(
                action="buy",
                trade=trade,
                provider=provider,
                force=force,
                confirm_token=confirm_token,
                payload=payload,
                runtime=runtime,
            )
        return self._execute_action(
            trade_id=trade_id,
            action="buy",
            provider=provider,
            payload=payload,
            dry_run=dry_run,
            force=force,
            webhook_url=settings.execution_webhook_buy_url.strip(),
            guard_error=guard_error,
            on_success_update=None,
        )

    def retry_failed(
        self,
        *,
        action: str | None = None,
        limit: int = 20,
        dry_run: bool = True,
        force: bool = False,
        confirm_token: str | None = None,
    ) -> dict[str, Any]:
        normalized_action = (action or "").strip().lower() or None
        if normalized_action and normalized_action not in {"buy", "list", "sell"}:
            raise ValueError("action must be one of buy/list/sell")
        if not self._retry_lock.acquire(blocking=False):
            self._mark_retry_busy("retry_failed_in_progress")
            raise BusyStateError(
                service="execution_retry_replay",
                reason="retry_failed_in_progress",
                message="retry_failed replay is already in progress",
            )

        try:
            rows = repo.list_latest_failed_execution_candidates(
                action=normalized_action,
                limit=max(1, min(200, int(limit))),
            )
            results: list[dict[str, Any]] = []
            retried = 0
            succeeded = 0
            failed = 0

            for row in rows:
                current_action = str(row["action"]).strip().lower()
                trade_id = int(row["trade_id"])
                retried += 1
                try:
                    request_payload = self._parse_request_payload(row["request_json"])
                    if current_action == "buy":
                        res = self.execute_buy(
                            trade_id=trade_id,
                            dry_run=dry_run,
                            force=force,
                            confirm_token=confirm_token,
                        )
                    elif current_action == "list":
                        res = self.execute_list(
                            trade_id=trade_id,
                            dry_run=dry_run,
                            force=force,
                            confirm_token=confirm_token,
                            listing_url=str(request_payload.get("requested_listing_url") or ""),
                            note="retry failed execution list",
                        )
                    elif current_action == "sell":
                        requested = request_payload.get("requested_sold_price")
                        sold_price: float | None = None
                        if requested is not None:
                            try:
                                val = float(requested)
                                sold_price = val if val > 0 else None
                            except (TypeError, ValueError):
                                sold_price = None
                        res = self.execute_sell(
                            trade_id=trade_id,
                            dry_run=dry_run,
                            force=force,
                            confirm_token=confirm_token,
                            sold_price=sold_price,
                            note="retry failed execution sell",
                        )
                    else:
                        raise RuntimeError(f"unsupported action: {current_action}")

                    ok = bool(res.get("success"))
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                    results.append(
                        {
                            "trade_id": trade_id,
                            "action": current_action,
                            "previous_log_id": int(row["id"]),
                            "success": ok,
                            "new_log_id": int(res.get("log_id") or 0),
                            "business_ban_code": str(res.get("business_ban_code") or ""),
                            "error": str(res.get("error") or ""),
                        }
                    )
                except Exception as exc:
                    failed += 1
                    results.append(
                        {
                            "trade_id": trade_id,
                            "action": current_action,
                            "previous_log_id": int(row["id"]),
                            "success": False,
                            "new_log_id": 0,
                            "business_ban_code": "",
                            "error": str(exc),
                        }
                    )

            return {
                "action": normalized_action or "all",
                "dry_run": dry_run,
                "force": force,
                "retried": retried,
                "succeeded": succeeded,
                "failed": failed,
                "items": results,
            }
        finally:
            self._retry_lock.release()

    def _execute_action(
        self,
        *,
        trade_id: int,
        action: str,
        provider: str,
        payload: dict[str, Any],
        dry_run: bool,
        force: bool,
        webhook_url: str,
        guard_error: str | None = None,
        on_success_update: Callable[[dict[str, Any], str], dict[str, Any] | None] | None = None,
    ) -> dict[str, Any]:
        idempotency_key = self._build_idempotency_key(action, trade_id, payload)

        if guard_error:
            response_payload = {
                "success": False,
                "provider": provider,
                "blocked": True,
                "reason": guard_error,
            }
            log_id = repo.create_execution_log(
                trade_id=trade_id,
                action=action,
                provider=provider,
                dry_run=dry_run,
                request_payload=payload,
                response_payload=response_payload,
                success=False,
                error=guard_error,
            )
            return {
                "log_id": log_id,
                "trade_id": trade_id,
                "action": action,
                "provider": provider,
                "dry_run": dry_run,
                "force": force,
                "success": False,
                "skipped": False,
                "blocked": True,
                "idempotency_key": idempotency_key,
                "external_id": "",
                "error": guard_error,
                "response": response_payload,
            }

        if not dry_run and not force:
            latest_success = repo.get_latest_execution_log(
                trade_id=trade_id,
                action=action,
                success_only=True,
            )
            if latest_success:
                response_payload = {
                    "success": True,
                    "provider": provider,
                    "skipped": True,
                    "reason": "already_executed",
                    "previous_log_id": int(latest_success["id"]),
                }
                log_id = repo.create_execution_log(
                    trade_id=trade_id,
                    action=action,
                    provider=provider,
                    dry_run=dry_run,
                    request_payload=payload,
                    response_payload=response_payload,
                    success=True,
                    error="",
                )
                return {
                    "log_id": log_id,
                    "trade_id": trade_id,
                    "action": action,
                    "provider": provider,
                    "dry_run": dry_run,
                    "force": force,
                    "success": True,
                    "skipped": True,
                    "blocked": False,
                    "idempotency_key": idempotency_key,
                    "external_id": "",
                    "error": "",
                    "response": response_payload,
                }

        success = False
        response_payload: dict[str, Any] = {}
        error = ""
        external_id = ""
        business_ban_code = ""

        try:
            success, response_payload, external_id, business_ban_code = self._dispatch_provider_execution(
                action=action,
                trade_id=trade_id,
                provider=provider,
                payload=payload,
                dry_run=dry_run,
                webhook_url=webhook_url,
                idempotency_key=idempotency_key,
            )
        except BusinessBanError as exc:
            error = str(exc)
            business_ban_code = str(exc.code or "")
            response_payload = {
                "error": error,
                "business_ban_code": business_ban_code,
                "context": exc.context,
            }
            success = False
        except Exception as exc:
            error = str(exc)
            response_payload = {"error": error}
            success = False

        if not success and not error:
            error = self._extract_error_message(response_payload)

        local_update: dict[str, Any] | None = None
        if success and not dry_run and on_success_update:
            try:
                local_update = on_success_update(response_payload, external_id) or {
                    "applied": False,
                    "reason": "no_state_update",
                }
            except Exception as exc:
                local_update = {
                    "applied": False,
                    "error": str(exc),
                }
        if local_update is not None:
            response_payload = {
                **response_payload,
                "local_update": local_update,
            }
        if business_ban_code:
            response_payload = {
                **response_payload,
                "business_ban_code": business_ban_code,
            }

        log_id = repo.create_execution_log(
            trade_id=trade_id,
            action=action,
            provider=provider,
            dry_run=dry_run,
            request_payload=payload,
            response_payload=response_payload,
            success=success,
            error=error,
        )

        return {
            "log_id": log_id,
            "trade_id": trade_id,
            "action": action,
            "provider": provider,
            "dry_run": dry_run,
            "force": force,
            "success": success,
            "skipped": False,
            "blocked": False,
            "idempotency_key": idempotency_key,
            "external_id": external_id,
            "error": error,
            "business_ban_code": business_ban_code,
            "response": response_payload,
        }

    def _dispatch_provider_execution(
        self,
        *,
        action: str,
        trade_id: int,
        provider: str,
        payload: dict[str, Any],
        dry_run: bool,
        webhook_url: str,
        idempotency_key: str,
    ) -> tuple[bool, dict[str, Any], str, str]:
        if dry_run or provider in {"disabled", "none"}:
            external_id = f"dryrun_{action}_{trade_id}_{uuid.uuid4().hex[:8]}"
            return (
                True,
                {
                    "success": True,
                    "provider": provider,
                    "external_id": external_id,
                    "message": "dry run, no external order sent",
                },
                external_id,
                "",
            )

        if provider == "mock":
            external_id = f"mock_{action}_{trade_id}_{uuid.uuid4().hex[:8]}"
            return (
                True,
                {
                    "success": True,
                    "provider": provider,
                    "external_id": external_id,
                    "message": f"mock provider {action} filled",
                },
                external_id,
                "",
            )

        if provider != "webhook":
            raise RuntimeError(f"unsupported provider: {provider}")

        if not webhook_url:
            raise RuntimeError(f"EXECUTION_WEBHOOK_{action.upper()}_URL is empty")

        max_attempts = max(1, settings.execution_webhook_max_retries + 1)
        body_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        attempts: list[dict[str, Any]] = []
        external_id = ""
        webhook_proxies = resolve_proxy_for_url(webhook_url)
        business_ban_code = ""

        for attempt in range(1, max_attempts + 1):
            headers = self._build_webhook_headers(
                body_text=body_text,
                idempotency_key=idempotency_key,
            )
            try:
                resp = request_post(
                    webhook_url,
                    data=body_text.encode("utf-8"),
                    timeout=settings.execution_timeout_sec,
                    headers=headers,
                    proxies=webhook_proxies,
                )
                try:
                    body = resp.json()
                except Exception:
                    body = {"raw_text": resp.text[:400]}
                attempts.append(
                    {
                        "attempt": attempt,
                        "status_code": resp.status_code,
                        "body": body,
                    }
                )

                ok = 200 <= resp.status_code < 300 and bool(body.get("success", True))
                if ok:
                    if isinstance(body, dict):
                        external_id = str(
                            body.get("external_id") or body.get("order_id") or ""
                        ).strip()
                    return (
                        True,
                        {
                            "status_code": resp.status_code,
                            "body": body,
                            "attempts": attempts,
                        },
                        external_id,
                        "",
                    )

                business_ban_code = self._detect_business_ban_code(
                    status_code=resp.status_code,
                    body=body if isinstance(body, dict) else {},
                )
                if business_ban_code:
                    self._on_business_ban(
                        action=action,
                        code=business_ban_code,
                        webhook_proxies=webhook_proxies,
                        reason=f"http_{resp.status_code}",
                    )
                    if attempt >= max_attempts:
                        raise BusinessBanError(
                            code=business_ban_code,
                            message=(
                                f"business ban detected while executing {action}: "
                                f"code={business_ban_code}"
                            ),
                            context=f"status={resp.status_code}",
                        )
                    webhook_proxies = resolve_proxy_for_url(webhook_url)
                    time.sleep(max(0.0, settings.execution_webhook_retry_backoff_sec) * attempt)
                    continue

                should_retry = (
                    self._should_retry_http_status(resp.status_code)
                    and attempt < max_attempts
                )
                if should_retry:
                    time.sleep(max(0.0, settings.execution_webhook_retry_backoff_sec) * attempt)
                    continue

                return (
                    False,
                    {
                        "status_code": resp.status_code,
                        "body": body,
                        "attempts": attempts,
                    },
                    external_id,
                    business_ban_code,
                )
            except requests.RequestException as exc:
                attempts.append(
                    {
                        "attempt": attempt,
                        "error": str(exc),
                    }
                )
                if webhook_proxies:
                    mark_proxy_bad(
                        proxy_url_from_mapping(webhook_proxies),
                        reason=f"webhook_exception:{str(exc)[:120]}",
                    )
                if attempt < max_attempts:
                    time.sleep(max(0.0, settings.execution_webhook_retry_backoff_sec) * attempt)
                    webhook_proxies = resolve_proxy_for_url(webhook_url)
                    continue
                raise RuntimeError(str(exc)) from exc

        return False, {"attempts": attempts}, external_id, business_ban_code

    def _build_webhook_headers(self, *, body_text: str, idempotency_key: str) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key,
        }
        token = settings.execution_auth_token.strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        secret = settings.execution_webhook_secret.strip()
        if secret:
            timestamp = str(int(time.time()))
            signature = self._hmac_sha256(secret, f"{timestamp}.{body_text}")
            headers["X-CardFlip-Timestamp"] = timestamp
            headers["X-CardFlip-Signature"] = signature
        return headers

    @staticmethod
    def _hmac_sha256(secret: str, text: str) -> str:
        return hmac.new(secret.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _build_idempotency_key(action: str, trade_id: int, payload: dict[str, Any]) -> str:
        payload_text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        raw = f"{action}:{trade_id}:{payload_text}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"cf_{action}_{trade_id}_{digest[:20]}"

    @staticmethod
    def _should_retry_http_status(status_code: int) -> bool:
        return status_code >= 500 or status_code in {408, 425, 429}

    @staticmethod
    def _extract_error_message(response_payload: dict[str, Any]) -> str:
        if not isinstance(response_payload, dict):
            return ""
        body = response_payload.get("body")
        if isinstance(body, dict):
            if body.get("error"):
                return str(body.get("error"))
            if body.get("message"):
                return str(body.get("message"))
        status_code = response_payload.get("status_code")
        if status_code:
            return f"http_status={status_code}"
        return ""

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _detect_business_ban_code(self, *, status_code: int, body: dict[str, Any]) -> str:
        if status_code in set(settings.execution_business_ban_status_codes):
            return f"http_{status_code}"

        if not isinstance(body, dict):
            return ""

        candidate_values: list[str] = []
        for key in ("code", "error_code", "biz_code", "bizCode", "sub_code", "status"):
            text = self._as_text(body.get(key))
            if text:
                candidate_values.append(text)
        message = self._as_text(body.get("message") or body.get("error") or body.get("msg"))
        if message:
            candidate_values.append(message)

        ban_tokens = {token.upper() for token in settings.execution_business_ban_codes}
        for candidate in candidate_values:
            upper = candidate.upper()
            if upper in ban_tokens:
                return candidate
            if any(token in upper for token in ban_tokens):
                return candidate

        return ""

    def _on_business_ban(
        self,
        *,
        action: str,
        code: str,
        webhook_proxies: dict[str, str] | None,
        reason: str,
    ) -> None:
        if not settings.execution_auto_rotate_proxy_on_ban:
            return
        proxy_url = proxy_url_from_mapping(webhook_proxies)
        if proxy_url:
            mark_proxy_bad(
                proxy_url,
                reason=f"business_ban:{action}:{code}:{reason}",
            )
        rotate_proxy(
            reason=f"business_ban:{action}:{code}:{reason}",
            required=False,
        )

    def _validate_live_action_guard(
        self,
        *,
        action: str,
        trade: Any,
        provider: str,
        force: bool,
        confirm_token: str | None,
        payload: dict[str, Any],
        runtime: dict[str, Any],
    ) -> str | None:
        trade_status = str(trade["status"] if "status" in trade.keys() else "").strip().lower()
        allowed_statuses = {
            "buy": {"approved_for_buy"},
            "list": {"approved_for_buy"},
            "sell": {"listed_for_sale"},
        }
        expected = allowed_statuses.get(action, set())
        if expected and trade_status not in expected and not force:
            return f"trade status {trade_status or 'unknown'} is not allowed for {action}"

        if provider in {"disabled", "none"}:
            return "EXECUTION_PROVIDER is disabled"

        if not bool(runtime.get("live_enabled")):
            return "EXECUTION_LIVE_ENABLED=false"

        configured_token = str(runtime.get("live_confirm_token") or "").strip()
        require_confirm = bool(runtime.get("live_confirm_required"))
        if require_confirm:
            if not configured_token:
                return "EXECUTION_LIVE_CONFIRM_TOKEN is empty while confirm is required"
            if (confirm_token or "").strip() != configured_token:
                return "invalid confirm token"

        if action == "buy":
            max_price = float(runtime.get("live_max_buy_price") or 0.0)
            buy_price = float(payload.get("buy_price") or 0.0)
            if max_price > 0 and buy_price > max_price:
                return (
                    f"approved_buy_price {buy_price:.2f} exceeds "
                    f"EXECUTION_LIVE_MAX_BUY_PRICE {max_price:.2f}"
                )
        elif action == "list":
            min_ratio = float(runtime.get("live_min_list_profit_ratio") or 0.0)
            if min_ratio > 0:
                buy_price = float(payload.get("buy_price") or 0.0)
                target_price = float(payload.get("target_sell_price") or 0.0)
                min_price = buy_price * (1.0 + min_ratio)
                if buy_price > 0 and target_price < min_price:
                    return (
                        f"target_sell_price {target_price:.2f} is below min list price "
                        f"{min_price:.2f} (EXECUTION_LIVE_MIN_LIST_PROFIT_RATIO={min_ratio:.4f})"
                    )
        elif action == "sell":
            min_ratio = float(runtime.get("live_min_sell_profit_ratio") or 0.0)
            if min_ratio > 0:
                buy_price = float(payload.get("buy_price") or 0.0)
                sell_price = float(
                    payload.get("requested_sold_price")
                    or payload.get("target_sell_price")
                    or 0.0
                )
                min_price = buy_price * (1.0 + min_ratio)
                if buy_price > 0 and sell_price < min_price:
                    return (
                        f"sold_price {sell_price:.2f} is below min sell price "
                        f"{min_price:.2f} (EXECUTION_LIVE_MIN_SELL_PROFIT_RATIO={min_ratio:.4f})"
                    )

        return None

    @staticmethod
    def _require_trade(trade_id: int) -> Any:
        trade = repo.get_trade(trade_id)
        if not trade:
            raise ValueError("Trade not found")
        return trade

    @staticmethod
    def _extract_body_map(response_payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(response_payload, dict):
            return {}
        body = response_payload.get("body")
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _parse_request_payload(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
            except Exception:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _resolve_listing_url(
        self,
        *,
        explicit_listing_url: str,
        response_payload: dict[str, Any],
        external_id: str,
        provider: str,
        trade: Any,
    ) -> str:
        explicit = (explicit_listing_url or "").strip()
        if explicit:
            return explicit

        body = self._extract_body_map(response_payload)
        for key in ("listing_url", "url", "item_url", "detail_url"):
            value = body.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text

        if "listing_url" in trade.keys():
            current = str(trade["listing_url"] or "").strip()
            if current:
                return current

        if external_id:
            return f"{provider}://list/{external_id}"
        return f"{provider}://list/{int(trade['id'])}"

    def _resolve_sold_price(
        self,
        *,
        requested_sold_price: float | None,
        response_payload: dict[str, Any],
        trade: Any,
    ) -> float:
        if requested_sold_price is not None and requested_sold_price > 0:
            return round(float(requested_sold_price), 2)

        body = self._extract_body_map(response_payload)
        for key in ("sold_price", "price", "deal_price", "final_price"):
            value = body.get(key)
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric > 0:
                return round(numeric, 2)

        fallback = float(trade["target_sell_price"] if "target_sell_price" in trade.keys() else 0.0)
        if fallback > 0:
            return round(fallback, 2)
        raise RuntimeError("unable to resolve sold_price for trade state update")


execution_service = ExecutionService()
