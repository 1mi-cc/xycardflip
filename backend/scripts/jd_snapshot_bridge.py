from __future__ import annotations

import sys

from snapshot_bridge_common import main as snapshot_bridge_main


if __name__ == "__main__":
    raise SystemExit(snapshot_bridge_main("jd", sys.argv[1:]))
