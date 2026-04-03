@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend\scripts\sync_xianyu_cookie_to_server.ps1" %*
