@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo [launcher] start_card_flip.bat entered

set "SCRIPT_DIR=%~dp0"
set "ROOT="
set "WITH_PROXY=false"
set "CHECK_ONLY=false"
set "FORCE_INSTALL=false"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3000"
set "PROXY_PORT=8899"
set "HAVE_CURL=false"
set "CURL_EXE=curl.exe"

for %%A in (%*) do (
  if /i "%%~A"=="proxy" set "WITH_PROXY=true"
  if /i "%%~A"=="check" set "CHECK_ONLY=true"
  if /i "%%~A"=="fresh" set "FORCE_INSTALL=true"
)

if defined CARD_FLIP_ROOT call :check_root "%CARD_FLIP_ROOT%"
if not defined ROOT call :check_root "%SCRIPT_DIR%"
if not defined ROOT call :search_up "%SCRIPT_DIR%"
if not defined ROOT call :check_root "%SCRIPT_DIR%xyzw_web_helper"
if not defined ROOT call :check_root "%SCRIPT_DIR%..\xyzw_web_helper"
if not defined ROOT call :check_root "%USERPROFILE%\Desktop\xyzw_web_helper"
if not defined ROOT call :probe_desktop
if not defined ROOT goto :root_not_found

echo [launcher] root=%ROOT%

echo [launcher] before cd
cd /d "%ROOT%" || goto :fail
echo [launcher] after cd

set "PKG=npm"
echo [launcher] package manager forced to npm (skip pnpm check due to corepack issue)
where curl >nul 2>nul
if not errorlevel 1 (
  set "HAVE_CURL=true"
  for %%C in (%SystemRoot%\System32\curl.exe curl.exe curl) do (
    if exist "%%~fC" set "CURL_EXE=%%~fC"
  )
)
echo [launcher] after curl check HAVE_CURL=%HAVE_CURL% CURL_EXE=%CURL_EXE%

echo [launcher] after package checks PKG=%PKG% curl=%HAVE_CURL%

set "BACKEND_REQ_HASH="
set "BACKEND_STAMP_FILE=backend\.venv\.requirements.sha256"
set "BACKEND_STAMP_VALUE="
set "INSTALL_BACKEND_DEPS=true"
echo [launcher] hashing backend\\requirements.txt
call :hash_file "backend\requirements.txt" BACKEND_REQ_HASH
if defined BACKEND_REQ_HASH set "BACKEND_STAMP_VALUE=%BACKEND_REQ_HASH%"
if "%FORCE_INSTALL%"=="false" (
  if defined BACKEND_STAMP_VALUE if exist "%BACKEND_STAMP_FILE%" (
    set /p "EXISTING_BACKEND_STAMP="<"%BACKEND_STAMP_FILE%"
    if /i "!EXISTING_BACKEND_STAMP!"=="!BACKEND_STAMP_VALUE!" set "INSTALL_BACKEND_DEPS=false"
  )
)

echo [launcher] compute front stamp
call :compute_front_stamp
set "FRONT_STAMP_FILE=node_modules\.deps.sha256"
set "INSTALL_FRONTEND_DEPS=true"
if "%FORCE_INSTALL%"=="false" (
  if exist "node_modules" (
    if defined FRONT_STAMP_VALUE if exist "%FRONT_STAMP_FILE%" (
      set /p "EXISTING_FRONT_STAMP="<"%FRONT_STAMP_FILE%"
      if /i "!EXISTING_FRONT_STAMP!"=="!FRONT_STAMP_VALUE!" set "INSTALL_FRONTEND_DEPS=false"
    ) else (
      set "INSTALL_FRONTEND_DEPS=false"
    )
  )
)

call :is_port_listening "%BACKEND_PORT%" BACKEND_PORT_IN_USE
call :is_port_listening "%FRONTEND_PORT%" FRONTEND_PORT_IN_USE
call :is_port_listening "%PROXY_PORT%" PROXY_PORT_IN_USE

echo.
echo === Card Flip Assistant Launcher ===
echo Script dir: %SCRIPT_DIR%
echo Project root: %ROOT%
echo Frontend package manager: %PKG%
echo Proxy pool enabled: %WITH_PROXY%
echo Check mode: %CHECK_ONLY%
echo Force dependency install: %FORCE_INSTALL%
echo curl available: %HAVE_CURL%
echo Backend deps install required: %INSTALL_BACKEND_DEPS%
echo Frontend deps install required: %INSTALL_FRONTEND_DEPS%
echo Port %BACKEND_PORT% in use: %BACKEND_PORT_IN_USE%
echo Port %FRONTEND_PORT% in use: %FRONTEND_PORT_IN_USE%
echo Port %PROXY_PORT% in use: %PROXY_PORT_IN_USE%
echo.

if "%CHECK_ONLY%"=="true" (
  echo Self-check completed.
  exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed or not in PATH.
  goto :fail
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm is not installed or not in PATH. Install Node.js first.
  goto :fail
)

if not exist "backend\.env" (
  copy /Y "backend\.env.example" "backend\.env" >nul
  echo Created backend\.env from template.
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating backend virtual environment...
  python -m venv "backend\.venv"
  if errorlevel 1 goto :fail
  set "INSTALL_BACKEND_DEPS=true"
)

if "%INSTALL_BACKEND_DEPS%"=="true" (
  echo Installing backend dependencies...
  "backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
  if errorlevel 1 goto :fail
  if defined BACKEND_STAMP_VALUE (
    >"%BACKEND_STAMP_FILE%" echo(!BACKEND_STAMP_VALUE!
  )
) else (
  echo Backend dependencies unchanged, skip install.
)

if "%INSTALL_FRONTEND_DEPS%"=="true" (
  echo Installing frontend dependencies...
  if "%PKG%"=="pnpm" (
    pnpm install --frozen-lockfile
    if errorlevel 1 (
      echo pnpm install failed, fallback to npm install...
      set "PKG=npm"
      npm install
      if errorlevel 1 goto :fail
    )
  ) else (
    npm install
    if errorlevel 1 goto :fail
  )
) else (
  echo Frontend dependencies unchanged, skip install.
)

if exist "node_modules" (
  call :compute_front_stamp
  if defined FRONT_STAMP_VALUE (
    >"%FRONT_STAMP_FILE%" echo(!FRONT_STAMP_VALUE!
  )
)

set "STARTED_PROXY=false"
set "STARTED_BACKEND=false"
set "STARTED_FRONTEND=false"

if "%WITH_PROXY%"=="true" (
  call :is_port_listening "%PROXY_PORT%" PROXY_PORT_IN_USE
  if "%PROXY_PORT_IN_USE%"=="true" (
    echo Port %PROXY_PORT% is already in use, skipping proxy pool startup.
  ) else (
    if exist "start_proxy_pool.bat" (
      echo Starting proxy pool at http://127.0.0.1:%PROXY_PORT% ...
      start "CardFlip ProxyPool" cmd /k "cd /d \"%ROOT%\" && start_proxy_pool.bat"
      set "STARTED_PROXY=true"
    ) else (
      echo start_proxy_pool.bat not found, skipping proxy pool.
    )
  )
)

call :is_port_listening "%BACKEND_PORT%" BACKEND_PORT_IN_USE
if "%BACKEND_PORT_IN_USE%"=="true" (
  echo Port %BACKEND_PORT% is already in use, skipping backend startup.
) else (
  echo Starting backend API at http://127.0.0.1:%BACKEND_PORT% ...
  start "CardFlip Backend" cmd /k "cd /d \"%ROOT%backend\" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port %BACKEND_PORT%"
  set "STARTED_BACKEND=true"
)

call :is_port_listening "%FRONTEND_PORT%" FRONTEND_PORT_IN_USE
if "%FRONTEND_PORT_IN_USE%"=="true" (
  echo Port %FRONTEND_PORT% is already in use, skipping frontend startup.
) else (
  echo Starting frontend at http://127.0.0.1:%FRONTEND_PORT% ...
  if "%PKG%"=="pnpm" (
    start "CardFlip Frontend" cmd /k "cd /d \"%ROOT%\" && pnpm run dev -- --host --port %FRONTEND_PORT%"
  ) else (
    start "CardFlip Frontend" cmd /k "cd /d \"%ROOT%\" && npm run dev -- --host --port %FRONTEND_PORT%"
  )
  set "STARTED_FRONTEND=true"
)

if "%STARTED_PROXY%"=="true" (
  call :wait_http "http://127.0.0.1:%PROXY_PORT%/" 30 "Proxy pool"
)
if "%STARTED_BACKEND%"=="true" (
  call :wait_http "http://127.0.0.1:%BACKEND_PORT%/health" 60 "Backend API"
)
if "%STARTED_FRONTEND%"=="true" (
  call :wait_http "http://127.0.0.1:%FRONTEND_PORT%/" 90 "Frontend UI"
)

echo.
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%/admin/card-flip-ops
echo Backend health: http://127.0.0.1:%BACKEND_PORT%/health
echo Backend docs: http://127.0.0.1:%BACKEND_PORT%/docs
exit /b 0

:wait_http
set "WAIT_URL=%~1"
set "WAIT_MAX=%~2"
set "WAIT_NAME=%~3"
if not defined WAIT_MAX set "WAIT_MAX=45"

if "%HAVE_CURL%"=="false" (
  echo curl is unavailable, skip health check for %WAIT_NAME%.
  exit /b 0
)

echo Waiting for %WAIT_NAME% ready: %WAIT_URL%
set /a "WAIT_I=0"
:wait_http_loop
set /a "WAIT_I+=1"
"%CURL_EXE%" -fsS --max-time 2 "%WAIT_URL%" >nul 2>nul
if not errorlevel 1 (
  echo %WAIT_NAME% is ready.
  exit /b 0
)
if !WAIT_I! GEQ %WAIT_MAX% (
  echo %WAIT_NAME% did not become ready in !WAIT_MAX!s.
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto :wait_http_loop

:is_port_listening
set "%~2=false"
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%~1 .*LISTENING"') do (
  set "%~2=true"
  goto :eof
)
exit /b 0

:compute_front_stamp
set "FRONT_LOCKFILE=package-lock.json"
if /i "%PKG%"=="pnpm" (
  if exist "pnpm-lock.yaml" set "FRONT_LOCKFILE=pnpm-lock.yaml"
)
set "FRONT_LOCK_HASH="
if exist "%FRONT_LOCKFILE%" (
  call :hash_file "%FRONT_LOCKFILE%" FRONT_LOCK_HASH
)
set "FRONT_STAMP_VALUE=%PKG%|%FRONT_LOCKFILE%|%FRONT_LOCK_HASH%"
exit /b 0

:hash_file
set "TARGET_FILE=%~1"
set "TARGET_VAR=%~2"
set "TARGET_HASH="
if not exist "%TARGET_FILE%" goto :hash_file_done
for /f "tokens=1" %%H in ('certutil -hashfile "%TARGET_FILE%" SHA256 ^| findstr /r /v /c:"hash of" /c:"CertUtil" /c:"^$"') do (
  set "TARGET_HASH=%%H"
  goto :hash_file_done
)
:hash_file_done
set "%TARGET_VAR%=%TARGET_HASH%"
exit /b 0

:check_root
set "CANDIDATE=%~1"
if not defined CANDIDATE exit /b 0
if not "%CANDIDATE:~-1%"=="\" set "CANDIDATE=%CANDIDATE%\"
if exist "%CANDIDATE%package.json" if exist "%CANDIDATE%backend\app\main.py" (
  set "ROOT=%CANDIDATE%"
)
exit /b 0

:search_up
set "CUR=%~1"
if not defined CUR exit /b 0
if not "%CUR:~-1%"=="\" set "CUR=%CUR%\"
:search_up_loop
if defined ROOT exit /b 0
call :check_root "%CUR%"
if defined ROOT exit /b 0
for %%I in ("%CUR%..") do set "PARENT=%%~fI\"
if /i "%PARENT%"=="%CUR%" exit /b 0
set "CUR=%PARENT%"
goto :search_up_loop

:probe_desktop
if not defined USERPROFILE exit /b 0
set "DESKTOP=%USERPROFILE%\Desktop"
if not exist "%DESKTOP%" exit /b 0
for /d %%D in ("%DESKTOP%\*") do (
  if not defined ROOT if exist "%%~fD\package.json" if exist "%%~fD\backend\app\main.py" set "ROOT=%%~fD\"
  if not defined ROOT for /d %%S in ("%%~fD\*") do (
    if not defined ROOT if exist "%%~fS\package.json" if exist "%%~fS\backend\app\main.py" set "ROOT=%%~fS\"
  )
)
exit /b 0

:root_not_found
echo.
echo Cannot locate project root automatically.
echo Please run this script from inside the project folder,
echo or set environment variable CARD_FLIP_ROOT to your project path.
goto :fail

:fail
echo.
echo Launch failed. Check the logs above.
pause
exit /b 1
