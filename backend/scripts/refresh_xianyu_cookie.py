from __future__ import annotations

import sys

from refresh_marketplace_cookie import main as refresh_marketplace_cookie_main


if __name__ == "__main__":
    raise SystemExit(
        refresh_marketplace_cookie_main(["--provider", "xianyu", *sys.argv[1:]])
    )
