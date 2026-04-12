from __future__ import annotations

import sys

from discover_marketplace_upstream import main as discover_upstream_main


if __name__ == "__main__":
    raise SystemExit(discover_upstream_main(["--provider", "pinduoduo", *sys.argv[1:]]))
