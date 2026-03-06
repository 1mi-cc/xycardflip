from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.supabase_sync import supabase_sync_service


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one Supabase sync cycle from local SQLite to Supabase."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when SUPABASE_ENABLED=false",
    )
    parser.add_argument(
        "--reset-cursors",
        action="store_true",
        help="Reset all cursors to 0 before sync.",
    )
    parser.add_argument(
        "--table",
        default="",
        help="Optional table name for cursor reset (works with --reset-cursors).",
    )
    args = parser.parse_args()

    if args.reset_cursors:
        result = supabase_sync_service.reset_cursors(table=args.table)
        print(json.dumps({"reset": result}, ensure_ascii=False, indent=2))
        if not result.get("ok"):
            return 2

    run_result = supabase_sync_service.run_once(force=args.force)
    print(json.dumps(run_result, ensure_ascii=False, indent=2))
    return 0 if bool(run_result.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
