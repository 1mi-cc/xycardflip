from __future__ import annotations

from pathlib import Path


SENSITIVE_KEYS = {
    "GEMINI_API_KEY",
    "RAGFLOW_API_KEY",
    "EXECUTION_AUTH_TOKEN",
    "EXECUTION_WEBHOOK_SECRET",
    "EXECUTION_LIVE_CONFIRM_TOKEN",
    "SMTP_PASSWORD",
    "XIAN_YU_COOKIE",
}


def _has_non_empty_sensitive_env(path: Path) -> list[str]:
    if not path.exists():
        return []
    bad: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        if key not in SENSITIVE_KEYS:
            continue
        if value.strip():
            bad.append(key)
    return bad


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    release_root = root / "release"
    backend_dist_root = root / "backend" / "dist"

    errors: list[str] = []

    for candidate in (release_root, backend_dist_root):
        if not candidate.exists():
            continue
        db_files = [p for p in candidate.rglob("*.db") if p.is_file()]
        for db in db_files:
            errors.append(f"db file should not exist in package artifacts: {db}")

        for env_file in candidate.rglob(".env"):
            bad_keys = _has_non_empty_sensitive_env(env_file)
            if bad_keys:
                errors.append(
                    f"sensitive env keys populated in {env_file}: {', '.join(sorted(set(bad_keys)))}"
                )

    if errors:
        print("release safety check failed:")
        for item in errors:
            print(f" - {item}")
        return 1

    print("release safety check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
