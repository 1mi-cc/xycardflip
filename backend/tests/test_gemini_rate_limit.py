"""Tests for GeminiClient rate-limit (HTTP 429) handling."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.gemini_client import GeminiClient, _RATE_LIMIT_BACKOFF_BASE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(keys: list[str]) -> GeminiClient:
    """Return a GeminiClient pre-loaded with *keys* without touching env/settings."""
    client = GeminiClient.__new__(GeminiClient)
    client.api_keys = keys
    client.model = "gemini-1.5-flash"
    client._key_index = 0
    client._rate_limited_until = {}
    client._rate_limit_strikes = {}
    return client


def _mock_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.request = MagicMock(spec=httpx.Request)
    if json_body is not None:
        resp.json.return_value = json_body
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=resp.request, response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# _mark_rate_limited / _clear_rate_limit / _next_key unit tests
# ---------------------------------------------------------------------------

def test_mark_rate_limited_sets_backoff() -> None:
    client = _make_client(["key1"])
    backoff = client._mark_rate_limited("key1")
    assert backoff == _RATE_LIMIT_BACKOFF_BASE
    assert client._rate_limited_until["key1"] > time.monotonic()
    assert client._rate_limit_strikes["key1"] == 1


def test_mark_rate_limited_exponential_backoff() -> None:
    client = _make_client(["key1"])
    b1 = client._mark_rate_limited("key1")
    b2 = client._mark_rate_limited("key1")
    b3 = client._mark_rate_limited("key1")
    assert b2 == b1 * 2
    assert b3 == b1 * 4


def test_clear_rate_limit_removes_quarantine() -> None:
    client = _make_client(["key1"])
    client._mark_rate_limited("key1")
    client._clear_rate_limit("key1")
    assert "key1" not in client._rate_limited_until
    assert "key1" not in client._rate_limit_strikes


def test_next_key_skips_rate_limited_key() -> None:
    client = _make_client(["key1", "key2"])
    # Quarantine key1 for a long time
    client._rate_limited_until["key1"] = time.monotonic() + 3600
    # First call should return key2 (key1 is skipped)
    assert client._next_key() == "key2"


def test_next_key_returns_soonest_expiring_when_all_limited() -> None:
    client = _make_client(["key1", "key2"])
    now = time.monotonic()
    client._rate_limited_until["key1"] = now + 5
    client._rate_limited_until["key2"] = now + 3600
    # Both are limited; should return key1 (expires sooner)
    result = client._next_key()
    assert result == "key1"


# ---------------------------------------------------------------------------
# extract_card_features integration tests (async, mocked HTTP)
# ---------------------------------------------------------------------------

GOOD_RESPONSE_BODY = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": '{"card_name":"Charizard","rarity":"UR","edition":"first","card_condition":"nm","extras":{},"confidence":0.95}'
                    }
                ]
            }
        }
    ]
}


@pytest.mark.asyncio
async def test_rotates_to_next_key_on_429() -> None:
    """If the first key gets 429 the client should try the second key."""
    client = _make_client(["bad_key", "good_key"])

    resp_429 = _mock_response(429)
    resp_200 = _mock_response(200, GOOD_RESPONSE_BODY)

    call_count = 0

    async def fake_post(url: str, **_kwargs):
        nonlocal call_count
        call_count += 1
        if "bad_key" in url:
            return resp_429
        return resp_200

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = fake_post

    with (
        patch("app.services.gemini_client.httpx.AsyncClient", return_value=mock_http),
        patch("app.services.gemini_client.resolve_proxy_for_url", return_value={}),
        patch("app.services.gemini_client.proxy_url_from_mapping", return_value=None),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await client.extract_card_features("Charizard Base Set", "Near mint condition")

    assert result is not None
    assert result["card_name"] == "Charizard"
    assert call_count == 2


@pytest.mark.asyncio
async def test_all_keys_rate_limited_returns_none() -> None:
    """If all keys are rate-limited the client should return None gracefully."""
    client = _make_client(["key1", "key2"])

    resp_429 = _mock_response(429)

    async def always_429(url: str, **_kwargs):
        return resp_429

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = always_429

    with (
        patch("app.services.gemini_client.httpx.AsyncClient", return_value=mock_http),
        patch("app.services.gemini_client.resolve_proxy_for_url", return_value={}),
        patch("app.services.gemini_client.proxy_url_from_mapping", return_value=None),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await client.extract_card_features("Any card", "")

    assert result is None
    # Both keys must have been quarantined
    assert "key1" in client._rate_limited_until
    assert "key2" in client._rate_limited_until


@pytest.mark.asyncio
async def test_successful_call_clears_rate_limit_state() -> None:
    """A successful call after recovery must clear the quarantine for that key."""
    client = _make_client(["key1"])
    # Pre-populate a stale rate-limit entry (already expired)
    client._rate_limited_until["key1"] = time.monotonic() - 1
    client._rate_limit_strikes["key1"] = 2

    resp_200 = _mock_response(200, GOOD_RESPONSE_BODY)

    async def always_200(url: str, **_kwargs):
        return resp_200

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = always_200

    with (
        patch("app.services.gemini_client.httpx.AsyncClient", return_value=mock_http),
        patch("app.services.gemini_client.resolve_proxy_for_url", return_value={}),
        patch("app.services.gemini_client.proxy_url_from_mapping", return_value=None),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await client.extract_card_features("Any card", "")

    assert result is not None
    assert "key1" not in client._rate_limited_until
    assert "key1" not in client._rate_limit_strikes


@pytest.mark.asyncio
async def test_no_keys_returns_none() -> None:
    client = _make_client([])
    result = await client.extract_card_features("title", "desc")
    assert result is None
