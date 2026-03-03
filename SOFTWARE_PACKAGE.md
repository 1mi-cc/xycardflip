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
- To disable browser auto-open, set `NO_AUTO_OPEN_BROWSER=1` before launching.

