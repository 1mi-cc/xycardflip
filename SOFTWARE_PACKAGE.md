# Software Packaging (Windows)

This project can be packaged as a desktop-ready bundle with one command:

```bat
build_software.bat
```

## Output

After packaging, files are generated under:

- `release/CardFlipAssistant/` (portable app folder)
- `release/start_card_flip_app.bat` (double-click launcher)
- `release/CardFlipAssistant_Windows.zip` (distribution archive)

## Runtime behavior

- The executable starts the FastAPI service.
- The built frontend is bundled and served by the backend.
- Browser opens automatically to `http://127.0.0.1:8000`.
- API paths work at both `/...` and `/card-api/...`.

## Notes

- Packaging uses PyInstaller in `backend/.venv_pack`.
- The generated `.env` in release removes `SQLITE_PATH` so packaged app uses writable defaults.
- The generated release `.env` leaves `UI_AUTH_PASSWORD` empty by default.
- On first launch, if `UI_AUTH_PASSWORD` is still empty, the app writes a one-time bootstrap password to `data/bootstrap_admin_credentials.json`.
- If you want the packaged app to auto-apply threshold tuning after forward-validation batches close, set `AUTO_TUNE_AUTO_APPLY_ENABLED=true` in the release `.env` and keep the cooldown / sample guard values explicit.
- The packaged app now exposes tuning history, tuning activity feed, and a 24h auto-tune report inside the card-flip ops console, so operators can audit why thresholds changed or why auto-tune was blocked.
- To disable browser auto-open, set `NO_AUTO_OPEN_BROWSER=1` before launching.

