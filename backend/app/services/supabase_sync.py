from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import requests

from ..config import settings
from ..database import get_conn

logger = logging.getLogger(__name__)


class SupabaseSyncService:
    TABLES: tuple[str, ...] = (
        "sales_raw",
        "listings_raw",
        "item_features",
        "valuation_records",
        "opportunities",
        "trades",
        "execution_logs",
        "opportunity_reject_logs",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._last_error = ""
        self._last_run_at = 0.0
        self._last_result: dict[str, Any] = {}
        self._cursors = {table: 0 for table in self.TABLES}
        self._load_state()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": settings.supabase_enabled,
                "configured": self._is_configured(),
                "is_running": self._thread is not None and self._thread.is_alive(),
                "sync_interval_sec": settings.supabase_sync_interval_sec,
                "batch_size": settings.supabase_sync_batch_size,
                "schema": settings.supabase_schema,
                "table_prefix": settings.supabase_table_prefix,
                "last_run_at_unix": self._last_run_at,
                "last_result": dict(self._last_result),
                "last_error": self._last_error,
                "cursors": dict(self._cursors),
            }

    def start(self) -> dict[str, Any]:
        reason = ""
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            if running:
                reason = "already_running"
            elif not settings.supabase_enabled:
                reason = "disabled"
            elif not self._is_configured():
                reason = "missing_config"
            else:
                self._stop_event.clear()
                self._thread = threading.Thread(
                    target=self._run_loop,
                    name="supabase-sync-service",
                    daemon=True,
                )
                self._thread.start()
        if reason:
            return {"started": False, "reason": reason, "status": self.status()}
        return {"started": True, "status": self.status()}

    def stop(self) -> dict[str, Any]:
        thread: threading.Thread | None
        with self._lock:
            thread = self._thread
            self._thread = None
            self._stop_event.set()

        if thread is not None:
            thread.join(timeout=3.0)
        return {"stopped": True, "status": self.status()}

    def run_once(self, force: bool = False) -> dict[str, Any]:
        if not force and not settings.supabase_enabled:
            return {"ok": True, "skipped": True, "reason": "disabled", "status": self.status()}
        if not self._is_configured():
            return {"ok": False, "skipped": True, "reason": "missing_config", "status": self.status()}

        started = time.time()
        total_uploaded = 0
        total_fetched = 0
        table_results: dict[str, dict[str, Any]] = {}

        try:
            for table in self.TABLES:
                result = self._sync_table(table)
                table_results[table] = result
                total_uploaded += int(result.get("uploaded", 0))
                total_fetched += int(result.get("fetched", 0))

            payload = {
                "ok": True,
                "skipped": False,
                "fetched": total_fetched,
                "uploaded": total_uploaded,
                "duration_ms": int((time.time() - started) * 1000),
                "tables": table_results,
            }
            with self._lock:
                self._last_error = ""
                self._last_result = payload
                self._last_run_at = time.time()
            return payload
        except Exception as exc:
            message = str(exc)
            with self._lock:
                self._last_error = message
                self._last_run_at = time.time()
            logger.exception("supabase sync run failed: %s", message)
            return {
                "ok": False,
                "skipped": False,
                "error": message,
                "duration_ms": int((time.time() - started) * 1000),
                "tables": table_results,
            }

    def reset_cursors(self, table: str | None = None) -> dict[str, Any]:
        selected_table = (table or "").strip()
        if selected_table and selected_table not in self.TABLES:
            return {
                "ok": False,
                "error": f"unsupported table: {selected_table}",
                "supported_tables": list(self.TABLES),
            }

        with self._lock:
            if selected_table:
                self._cursors[selected_table] = 0
            else:
                self._cursors = {name: 0 for name in self.TABLES}
        self._save_state()
        return {"ok": True, "table": selected_table or "all", "status": self.status()}

    def _run_loop(self) -> None:
        logger.info("supabase sync service started")
        while not self._stop_event.is_set():
            try:
                self.run_once(force=True)
            except Exception as exc:  # pragma: no cover
                with self._lock:
                    self._last_error = str(exc)
                    self._last_run_at = time.time()
                logger.exception("supabase sync loop error: %s", exc)
            wait_sec = max(5, int(settings.supabase_sync_interval_sec))
            if self._stop_event.wait(timeout=wait_sec):
                break
        logger.info("supabase sync service stopped")

    def _sync_table(self, table: str) -> dict[str, Any]:
        if table not in self.TABLES:
            raise ValueError(f"unsupported table: {table}")

        fetched = 0
        uploaded = 0
        cursor = self._cursors.get(table, 0)
        max_cursor = cursor
        batch_size = max(1, int(settings.supabase_sync_batch_size))
        loops = 0

        while loops < 200:
            loops += 1
            rows = self._fetch_rows_after_id(table=table, last_id=max_cursor, limit=batch_size)
            if not rows:
                break
            fetched += len(rows)
            response = self._upsert_rows(table=table, rows=rows)
            if not response.get("ok"):
                raise RuntimeError(
                    f"supabase upsert failed for {table}: {response.get('error') or response.get('status')}"
                )
            uploaded += len(rows)
            max_cursor = max(int(row.get("id", 0) or 0) for row in rows)
            if len(rows) < batch_size:
                break

        if max_cursor > cursor:
            with self._lock:
                self._cursors[table] = max_cursor
            self._save_state()

        return {
            "fetched": fetched,
            "uploaded": uploaded,
            "cursor_before": cursor,
            "cursor_after": max_cursor,
        }

    def _fetch_rows_after_id(self, table: str, last_id: int, limit: int) -> list[dict[str, Any]]:
        query = f"SELECT * FROM {table} WHERE id > ? ORDER BY id ASC LIMIT ?"
        with get_conn() as conn:
            rows = conn.execute(query, (int(last_id), int(limit))).fetchall()
        return [dict(row) for row in rows]

    def _upsert_rows(self, table: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"ok": True, "status": 200}
        endpoint = self._rest_endpoint(self._remote_table(table))
        headers = self._headers(prefer_merge=True)
        try:
            resp = requests.post(
                endpoint,
                headers=headers,
                params={"on_conflict": "id"},
                json=rows,
                timeout=max(1.0, float(settings.supabase_timeout_sec)),
            )
        except Exception as exc:
            return {"ok": False, "status": 0, "error": str(exc)}

        ok = resp.status_code in {200, 201, 204}
        return {
            "ok": ok,
            "status": resp.status_code,
            "error": "" if ok else resp.text[:400],
        }

    def _headers(self, *, prefer_merge: bool = False) -> dict[str, str]:
        key = settings.supabase_service_role_key.strip()
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Profile": settings.supabase_schema.strip() or "public",
            "Content-Profile": settings.supabase_schema.strip() or "public",
        }
        if prefer_merge:
            headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        return headers

    def _rest_endpoint(self, table: str) -> str:
        base = settings.supabase_url.strip().rstrip("/")
        return f"{base}/rest/v1/{table}"

    def _remote_table(self, local_table: str) -> str:
        prefix = "".join(
            ch for ch in str(settings.supabase_table_prefix or "cardflip_") if ch.isalnum() or ch == "_"
        )
        return f"{prefix}{local_table}"

    def _is_configured(self) -> bool:
        return bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip())

    def _state_file(self) -> Path:
        sqlite_path = Path(settings.sqlite_path).expanduser()
        return sqlite_path.parent / "supabase_sync_state.json"

    def _load_state(self) -> None:
        path = self._state_file()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        cursors = payload.get("cursors")
        if isinstance(cursors, dict):
            for table in self.TABLES:
                try:
                    value = int(cursors.get(table, 0))
                except Exception:
                    value = 0
                self._cursors[table] = max(0, value)

    def _save_state(self) -> None:
        path = self._state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = {"cursors": dict(self._cursors)}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


supabase_sync_service = SupabaseSyncService()
