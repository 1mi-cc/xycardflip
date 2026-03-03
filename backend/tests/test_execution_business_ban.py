from __future__ import annotations

from app.services.execution import ExecutionService


def test_detect_business_ban_by_http_status() -> None:
    svc = ExecutionService()
    code = svc._detect_business_ban_code(status_code=403, body={"success": False})
    assert code == "http_403"


def test_detect_business_ban_by_body_code() -> None:
    svc = ExecutionService()
    code = svc._detect_business_ban_code(
        status_code=200,
        body={"success": False, "code": "RISK_BLOCK"},
    )
    assert code == "RISK_BLOCK"
