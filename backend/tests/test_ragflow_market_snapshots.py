from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
import app.routers.ragflow as ragflow_router_module


def test_ragflow_upload_market_snapshots_endpoint(monkeypatch) -> None:
    temp_dir = tempfile.TemporaryDirectory()
    doc_path = Path(temp_dir.name) / "snapshot.md"
    doc_path.write_text("# Snapshot\n", encoding="utf-8")
    captured_kwargs: dict[str, object] = {}

    monkeypatch.setattr(
        ragflow_router_module,
        "write_market_snapshot_docs",
        lambda **kwargs: captured_kwargs.update(kwargs) or (
            temp_dir,
            [str(doc_path)],
            [
                {
                    "normalized_key": "manual_fragment:test",
                    "title": "功法残卷",
                    "filename": "snapshot.md",
                    "content": "# Snapshot\n",
                    "snapshot": {"normalized_key": "manual_fragment:test", "is_tradable": True},
                    "scope": kwargs.get("scope", "tradable"),
                }
            ],
        ),
    )
    monkeypatch.setattr(
        ragflow_router_module.ragflow_client,
        "ensure_market_dataset",
        lambda **kwargs: {"id": "dataset-1", "name": "cardflip_market_knowledge"},
    )
    monkeypatch.setattr(
        ragflow_router_module.ragflow_client,
        "upload_documents",
        lambda **kwargs: [{"id": "doc-1", "name": "snapshot.md"}],
    )
    parsed_ids: list[str] = []
    monkeypatch.setattr(
        ragflow_router_module.ragflow_client,
        "parse_documents",
        lambda **kwargs: parsed_ids.extend(kwargs.get("document_ids") or []),
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/ragflow/datasets/upload-market-snapshots",
            json={
                "dataset_name": "cardflip_market_knowledge",
                "limit": 5,
                "listing_hours": 24,
                "sales_days": 7,
                "auto_parse": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == "dataset-1"
    assert payload["generated"] == 1
    assert payload["uploaded"] == 1
    assert payload["parsed"] == 1
    assert payload["scope"] == "tradable"
    assert captured_kwargs["scope"] == "tradable"
    assert parsed_ids == ["doc-1"]
