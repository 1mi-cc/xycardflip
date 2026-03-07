@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "BASE_DIR=%~dp0"
set "ROOT_DIR="
set "PROXY_STARTER="
set "PROXY_PORT=8899"
set "AUTO_START_PROXY=true"
set "APP_DIR="

for /f "delims=" %%D in ('dir /b /ad /o-d "%BASE_DIR%CardFlipAssistant*" 2^>nul') do (
  if exist "%BASE_DIR%%%D\CardFlipAssistant.exe" (
    set "APP_DIR=%BASE_DIR%%%D"
    goto :app_found
  )
)

:app_found
if "%APP_DIR%"=="" (
  echo Cannot find CardFlipAssistant executable folder under "%BASE_DIR%"
  pause
  exit /b 1
)
if not exist "%APP_DIR%\CardFlipAssistant.exe" (
  echo Cannot find "%APP_DIR%\CardFlipAssistant.exe"
  pause
  exit /b 1
)

set "APP_ENV_FILE=%APP_DIR%\.env"
set "APP_ENV_TEMPLATE=%APP_DIR%\.env.example"
for %%I in ("%BASE_DIR%..") do set "ROOT_DIR=%%~fI\"
set "PROXY_STARTER=%ROOT_DIR%start_proxy_pool.bat"

if not exist "%APP_ENV_FILE%" (
  if exist "%APP_ENV_TEMPLATE%" (
    copy /Y "%APP_ENV_TEMPLATE%" "%APP_DIR%\.env" >nul
    echo [INFO] Created package .env from .env.example. Please review admin credentials before first use.
  ) else (
    echo [WARN] Missing package .env and .env.example in "%APP_DIR%"
  )
)

if exist "%APP_ENV_FILE%" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /I /B "MONITOR_USE_PROXY_POOL=" "%APP_ENV_FILE%"`) do (
    call :normalize_bool "%%B" AUTO_START_PROXY
  )
)

if /I "%AUTO_START_PROXY%"=="true" (
  call :is_port_listening "%PROXY_PORT%" PROXY_READY
  if /I not "!PROXY_READY!"=="true" (
    if exist "%PROXY_STARTER%" (
      echo [INFO] Starting proxy pool...
      start "CardFlip Proxy Pool" /min cmd /c ""%PROXY_STARTER%" > "%BASE_DIR%proxy_pool.log" 2>&1"
      call :wait_port "%PROXY_PORT%" 20 PROXY_READY
      if /I not "!PROXY_READY!"=="true" (
        echo [WARN] Proxy pool did not become ready on port %PROXY_PORT% within 20s.
      ) else (
        echo [INFO] Proxy pool is ready on port %PROXY_PORT%.
      )
    ) else (
      echo [WARN] Proxy starter not found: "%PROXY_STARTER%"
    )
  ) else (
    echo [INFO] Proxy pool already listening on port %PROXY_PORT%.
  )
) else (
  echo [INFO] MONITOR_USE_PROXY_POOL=false, skip proxy auto-start.
)

if exist "%APP_ENV_FILE%" (
  set "DOTENV_PATH=%APP_ENV_FILE%"
  echo [INFO] DOTENV_PATH=%DOTENV_PATH%
)

if not exist "%APP_DIR%\data" mkdir "%APP_DIR%\data"
cd /d "%APP_DIR%"
start "" "CardFlipAssistant.exe"
exit /b 0

:normalize_bool
setlocal
set "RAW=%~1"
set "RAW=%RAW:"=%"
set "RAW=%RAW: =%"
if /I "%RAW%"=="1" (set "NORMALIZED=true") else if /I "%RAW%"=="true" (set "NORMALIZED=true") else if /I "%RAW%"=="yes" (set "NORMALIZED=true") else if /I "%RAW%"=="on" (set "NORMALIZED=true") else (set "NORMALIZED=false")
endlocal & set "%~2=%NORMALIZED%"
exit /b 0

:is_port_listening
set "%~2=false"
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%~1 .*LISTENING"') do (
  set "%~2=true"
  goto :eof
)
exit /b 0

:wait_port
setlocal EnableDelayedExpansion
set "WAIT_PORT=%~1"
set /a "WAIT_RETRIES=%~2"
:wait_loop
call :is_port_listening "!WAIT_PORT!" WAIT_READY
if /I "!WAIT_READY!"=="true" (
  endlocal & set "%~3=true"
  exit /b 0
)
set /a "WAIT_RETRIES-=1"
if !WAIT_RETRIES! LEQ 0 (
  endlocal & set "%~3=false"
  exit /b 0
)
timeout /t 1 >nul
goto :wait_loop
