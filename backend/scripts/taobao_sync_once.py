from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import repositories as repo
from app.services.marketplace_taobao import taobao_top_client


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one Taobao TOP read-only sync and write normalized offers into marketplace_offers."
    )
    parser.add_argument(
        "--query-string",
        default="",
        help="Optional TAOBAO_TOP_QUERY_STRING override.",
    )
    args = parser.parse_args()

    result = taobao_top_client.sync_once(query_string_override=args.query_string)
    inserted = repo.insert_marketplace_offers(result["rows"])
    print(
        json.dumps(
            {
                "count": int(result.get("count") or 0),
                "inserted": int(inserted),
                "platform": "taobao",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if inserted >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
