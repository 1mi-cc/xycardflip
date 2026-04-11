@echo off
setlocal

set ROOT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%ROOT_DIR%backend\scripts\run_browser_session_keeper.ps1" -Provider pinduoduo %*

endlocal
