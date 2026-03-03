from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from ..config import settings
from .proxy_resolver import request_get
from .proxy_resolver import request_post
from .proxy_resolver import resolve_proxy_for_url


class CookieProvider:
    """
    Retrieves Xianyu cookies either from env or a local cookie service.
    Caches the latest cookie string in memory with a TTL to avoid hammering
    the automation service.
    """

    def __init__(self) -> None:
        self._cached_cookie: str | None = settings.xianyu_cookie.strip() or None
        self._last_fetched: float = 0.0
        self._ttl: int = max(60, settings.xianyu_cookie_ttl_sec)
        self._last_error: str = ""
        self._backend_root = Path(__file__).resolve().parents[2]

    def _resolve_env_path(self) -> Path:
        env_override = os.getenv("DOTENV_PATH", "").strip()
        if env_override:
            return Path(env_override).expanduser()
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent / ".env"
        return self._backend_root / ".env"

    def _resolve_refresh_script_path(self) -> Path:
        return self._backend_root / "scripts" / "refresh_xianyu_cookie.py"

    def _read_cookie_from_env(self) -> str:
        env_path = self._resolve_env_path()
        if not env_path.exists():
            return ""
        try:
            env_values = dotenv_values(env_path)
        except Exception:
            return ""
        return str(env_values.get("XIAN_YU_COOKIE") or "").strip()

    @property
    def last_error(self) -> str:
        return self._last_error

    def refresh_cookie_local(self, kill_browsers: bool = True) -> dict[str, Any]:
        script_path = self._resolve_refresh_script_path()
        if not script_path.exists():
            self._last_error = f"refresh script not found: {script_path}"
            return {
                "success": False,
                "error": self._last_error,
                "cookie_len": len(self._cached_cookie or ""),
                "has_m_h5_tk": "_m_h5_tk=" in (self._cached_cookie or ""),
                "has_m_h5_tk_enc": "_m_h5_tk_enc=" in (self._cached_cookie or ""),
            }

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run-script", str(script_path)]
        else:
            cmd = [sys.executable, str(script_path)]
        if kill_browsers:
            cmd.append("--kill-browsers")

        env = os.environ.copy()
        env_path = str(self._resolve_env_path())
        env["COOKIE_ENV_PATH"] = env_path
        env["DOTENV_PATH"] = env_path

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._backend_root),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                env=env,
            )
        except Exception as exc:
            self._last_error = str(exc)
            return {
                "success": False,
                "error": self._last_error,
                "cookie_len": len(self._cached_cookie or ""),
                "has_m_h5_tk": "_m_h5_tk=" in (self._cached_cookie or ""),
                "has_m_h5_tk_enc": "_m_h5_tk_enc=" in (self._cached_cookie or ""),
            }

        stdout_text = (proc.stdout or "").strip()
        stderr_text = (proc.stderr or "").strip()
        if proc.returncode != 0:
            self._last_error = stderr_text or stdout_text or f"exit code {proc.returncode}"
            return {
                "success": False,
                "error": self._last_error,
                "return_code": proc.returncode,
                "stdout": stdout_text[-500:],
                "stderr": stderr_text[-500:],
                "cookie_len": len(self._cached_cookie or ""),
                "has_m_h5_tk": "_m_h5_tk=" in (self._cached_cookie or ""),
                "has_m_h5_tk_enc": "_m_h5_tk_enc=" in (self._cached_cookie or ""),
            }

        cookie_text = self._read_cookie_from_env()
        if not cookie_text:
            self._last_error = "refresh succeeded but XIAN_YU_COOKIE not found in .env"
            return {
                "success": False,
                "error": self._last_error,
                "return_code": proc.returncode,
                "stdout": stdout_text[-500:],
                "stderr": stderr_text[-500:],
                "cookie_len": len(self._cached_cookie or ""),
                "has_m_h5_tk": "_m_h5_tk=" in (self._cached_cookie or ""),
                "has_m_h5_tk_enc": "_m_h5_tk_enc=" in (self._cached_cookie or ""),
            }

        self._cached_cookie = cookie_text
        self._last_fetched = time.time()
        self._last_error = ""
        return {
            "success": True,
            "return_code": proc.returncode,
            "stdout": stdout_text[-500:],
            "stderr": stderr_text[-500:],
            "cookie_len": len(cookie_text),
            "has_m_h5_tk": "_m_h5_tk=" in cookie_text,
            "has_m_h5_tk_enc": "_m_h5_tk_enc=" in cookie_text,
        }

    def get_cookie(self, force_refresh: bool = False) -> str | None:
        if self._cached_cookie and not force_refresh:
            if (time.time() - self._last_fetched) < self._ttl:
                return self._cached_cookie

        # If env provided, reuse even if TTL expired (no refresh endpoint needed)
        if settings.xianyu_cookie.strip() and not force_refresh:
            self._cached_cookie = settings.xianyu_cookie.strip()
            self._last_fetched = time.time()
            return self._cached_cookie

        if settings.xianyu_cookie_refresh_on_start and settings.xianyu_cookie_refresh_url:
            try:
                refresh_proxies = resolve_proxy_for_url(settings.xianyu_cookie_refresh_url)
                request_post(
                    settings.xianyu_cookie_refresh_url,
                    timeout=8,
                    proxies=refresh_proxies,
                )
            except Exception:
                # ignore refresh failure, fallback to latest endpoint
                pass

        if not settings.xianyu_cookie_provider_url:
            self._last_error = "cookie provider url not set"
            return self._cached_cookie

        try:
            provider_proxies = resolve_proxy_for_url(settings.xianyu_cookie_provider_url)
            resp = request_get(
                settings.xianyu_cookie_provider_url,
                timeout=8,
                proxies=provider_proxies,
            )
            if resp.status_code != 200:
                self._last_error = f"cookie provider status {resp.status_code}"
                return self._cached_cookie
            data = resp.json()
            cookie_str = str(data.get("cookie_string") or "").strip()
            if cookie_str:
                self._cached_cookie = cookie_str
                self._last_fetched = time.time()
                self._last_error = ""
                return self._cached_cookie
            self._last_error = "cookie_string missing in provider response"
            return self._cached_cookie
        except Exception as exc:
            self._last_error = str(exc)
            return self._cached_cookie
