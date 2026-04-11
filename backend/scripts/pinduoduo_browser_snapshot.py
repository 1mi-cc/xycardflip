from __future__ import annotations

import sys

from browser_snapshot_bridge import main as browser_snapshot_bridge_main


if __name__ == "__main__":
    raise SystemExit(browser_snapshot_bridge_main("pinduoduo", sys.argv[1:]))
