@echo off
setlocal

set ROOT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%ROOT_DIR%backend\scripts\run_cookie_bridge.ps1" -Provider jd %*

endlocal
