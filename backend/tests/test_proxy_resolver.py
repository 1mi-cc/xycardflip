from __future__ import annotations

from app.config import settings
from app.services import proxy_resolver as pr


def test_parse_pool_proxies_supports_json_shapes() -> None:
    raw = '[["1.1.1.1",8080],{"ip":"2.2.2.2","port":9090},{"host":"3.3.3.3","port":"3128"}]'
    parsed = pr._parse_pool_proxies(raw)
    assert ("1.1.1.1", "8080") in parsed
    assert ("2.2.2.2", "9090") in parsed
    assert ("3.3.3.3", "3128") in parsed


def test_mark_proxy_bad_quarantines_after_threshold() -> None:
    old_max_failures = settings.proxy_max_failures
    old_ttl = settings.proxy_bad_ttl_sec
    try:
        object.__setattr__(settings, "proxy_max_failures", 1)
        object.__setattr__(settings, "proxy_bad_ttl_sec", 60)
        result = pr.mark_proxy_bad("http://9.9.9.9:8080", reason="unit_test")
        assert result["marked"] is True
        runtime = pr.network_policy_status()["runtime"]
        assert "http://9.9.9.9:8080" in runtime["quarantined_proxies"]
    finally:
        object.__setattr__(settings, "proxy_max_failures", old_max_failures)
        object.__setattr__(settings, "proxy_bad_ttl_sec", old_ttl)
