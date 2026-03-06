@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "COMPOSE_FILE=%ROOT%monitoring\uptime-kuma\docker-compose.yml"
set "UPTIME_KUMA_PORT=%UPTIME_KUMA_PORT%"
if "%UPTIME_KUMA_PORT%"=="" set "UPTIME_KUMA_PORT=3001"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is not installed or not in PATH.
  exit /b 1
)

if not exist "%COMPOSE_FILE%" (
  echo Cannot find "%COMPOSE_FILE%"
  exit /b 1
)

echo Starting Uptime Kuma on port %UPTIME_KUMA_PORT%...
docker compose -f "%COMPOSE_FILE%" up -d
if errorlevel 1 (
  echo Failed to start Uptime Kuma.
  exit /b 1
)

echo Uptime Kuma is running: http://127.0.0.1:%UPTIME_KUMA_PORT%
exit /b 0
