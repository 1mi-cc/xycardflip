from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    parser = argparse.ArgumentParser(description="Read-only SQLite diagnostics for Card Flip Assistant.")
    parser.add_argument(
        "--sqlite-path",
        default="",
        help="Optional path to SQLite database. Defaults to current SQLITE_PATH/app config.",
    )
    parser.add_argument(
        "--no-query-plans",
        action="store_true",
        help="Skip EXPLAIN QUERY PLAN output.",
    )
    args = parser.parse_args()

    if args.sqlite_path:
        os.environ["SQLITE_PATH"] = str(Path(args.sqlite_path).expanduser())

    from app.database import collect_database_diagnostics  # noqa: PLC0415

    payload = collect_database_diagnostics(include_query_plans=not args.no_query_plans)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("available") else 1


if __name__ == "__main__":
    raise SystemExit(main())
