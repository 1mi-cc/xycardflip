@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "WITH_PROXY=false"
set "CHECK_ONLY=false"
set "FORCE_INSTALL=false"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3000"
set "PROXY_PORT=8899"
set "PKG=npm"

call :parse_args %*

cd /d "%ROOT%" || goto :fail

if not exist "package.json" (
  echo [ERROR] package.json not found under "%ROOT%"
  goto :fail
)
if not exist "backend\app\main.py" (
  echo [ERROR] backend\app\main.py not found under "%ROOT%"
  goto :fail
)

call :is_port_listening %BACKEND_PORT% BACKEND_PORT_IN_USE
call :is_port_listening %FRONTEND_PORT% FRONTEND_PORT_IN_USE
call :is_port_listening %PROXY_PORT% PROXY_PORT_IN_USE

echo.
echo === Card Flip Assistant Dev Launcher ===
echo Root: %ROOT%
echo Package manager: %PKG%
echo Proxy pool enabled: %WITH_PROXY%
echo Check only: %CHECK_ONLY%
echo Force install: %FORCE_INSTALL%
echo Backend port %BACKEND_PORT% in use: %BACKEND_PORT_IN_USE%
echo Frontend port %FRONTEND_PORT% in use: %FRONTEND_PORT_IN_USE%
echo Proxy port %PROXY_PORT% in use: %PROXY_PORT_IN_USE%
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed or not in PATH.
  goto :fail
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm is not installed or not in PATH.
  goto :fail
)

if not exist "backend\.env" (
  if exist "backend\.env.example" (
    copy /Y "backend\.env.example" "backend\.env" >nul
    echo [INFO] Created backend\.env from backend\.env.example
  ) else (
    echo [ERROR] backend\.env and backend\.env.example are both missing.
    goto :fail
  )
)

if "%CHECK_ONLY%"=="true" (
  echo [OK] Self-check completed.
  exit /b 0
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [INFO] Creating backend virtual environment...
  python -m venv "backend\.venv"
  if errorlevel 1 goto :fail
)

if "%FORCE_INSTALL%"=="true" goto :install_backend
if not exist "backend\.venv\.deps.ok" goto :install_backend
goto :after_backend_install

:install_backend
echo [INFO] Installing backend dependencies...
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto :fail
>"backend\.venv\.deps.ok" echo ok

:after_backend_install
if "%FORCE_INSTALL%"=="true" goto :install_frontend
if not exist "node_modules" goto :install_frontend
goto :after_frontend_install

:install_frontend
echo [INFO] Installing frontend dependencies...
npm install
if errorlevel 1 goto :fail

:after_frontend_install
if /I "%WITH_PROXY%"=="true" (
  call :is_port_listening %PROXY_PORT% PROXY_PORT_IN_USE
  if /I "%PROXY_PORT_IN_USE%"=="false" if exist "start_proxy_pool.bat" (
    echo [INFO] Starting proxy pool...
    start "CardFlip ProxyPool" /d "%ROOT%" cmd /k "call start_proxy_pool.bat"
  )
)

call :is_port_listening %BACKEND_PORT% BACKEND_PORT_IN_USE
if /I "%BACKEND_PORT_IN_USE%"=="true" (
  echo [WARN] Backend port %BACKEND_PORT% is already in use. Skip backend startup.
) else (
  echo [INFO] Starting backend...
  start "CardFlip Backend" /d "%ROOT%backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%"
)

call :is_port_listening %FRONTEND_PORT% FRONTEND_PORT_IN_USE
if /I "%FRONTEND_PORT_IN_USE%"=="true" (
  echo [WARN] Frontend port %FRONTEND_PORT% is already in use. Skip frontend startup.
) else (
  echo [INFO] Starting frontend...
  start "CardFlip Frontend" /d "%ROOT%" cmd /k "npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"
)

echo.
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%/admin/card-flip-ops
echo Backend docs: http://127.0.0.1:%BACKEND_PORT%/docs
echo Backend health: http://127.0.0.1:%BACKEND_PORT%/health
echo.
echo [OK] Launcher finished. Backend and frontend open in separate windows.
exit /b 0

:parse_args
if "%~1"=="" exit /b 0
if /I "%~1"=="proxy" set "WITH_PROXY=true"
if /I "%~1"=="check" set "CHECK_ONLY=true"
if /I "%~1"=="fresh" set "FORCE_INSTALL=true"
shift
goto :parse_args

:is_port_listening
set "%~2=false"
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%~1 .*LISTENING"') do (
  set "%~2=true"
  goto :eof
)
exit /b 0

:fail
echo.
echo [FAIL] Launch failed.
pause
exit /b 1
