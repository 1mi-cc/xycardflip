@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "COMPOSE_FILE=%ROOT%monitoring\uptime-kuma\docker-compose.yml"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is not installed or not in PATH.
  exit /b 1
)

if not exist "%COMPOSE_FILE%" (
  echo Cannot find "%COMPOSE_FILE%"
  exit /b 1
)

echo Stopping Uptime Kuma...
docker compose -f "%COMPOSE_FILE%" down
if errorlevel 1 (
  echo Failed to stop Uptime Kuma.
  exit /b 1
)

echo Uptime Kuma stopped.
exit /b 0
