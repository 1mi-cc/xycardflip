@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "ROOT="
set "CHECK_ONLY=false"
set "FORCE_INSTALL=false"
set "PROXY_PORT=8899"

for %%A in (%*) do (
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

set "POOL_DIR=%ROOT%third_party\IPProxyPool"
if not exist "%POOL_DIR%\IPProxy.py" (
  echo IPProxyPool not found at %POOL_DIR%
  exit /b 1
)

set "POOL_REQ_HASH="
set "POOL_STAMP_FILE=%POOL_DIR%\.venv\.requirements.sha256"
set "POOL_STAMP_VALUE="
set "INSTALL_PROXY_DEPS=true"
call :hash_file "%POOL_DIR%\requirements.txt" POOL_REQ_HASH
if defined POOL_REQ_HASH set "POOL_STAMP_VALUE=%POOL_REQ_HASH%"
if "%FORCE_INSTALL%"=="false" (
  if defined POOL_STAMP_VALUE if exist "%POOL_STAMP_FILE%" (
    set /p "EXISTING_PROXY_STAMP="<"%POOL_STAMP_FILE%"
    if /i "!EXISTING_PROXY_STAMP!"=="!POOL_STAMP_VALUE!" set "INSTALL_PROXY_DEPS=false"
  )
)
call :is_port_listening "%PROXY_PORT%" PROXY_PORT_IN_USE

echo.
echo === Proxy Pool Launcher ===
echo Script dir: %SCRIPT_DIR%
echo Project root: %ROOT%
echo Pool dir: %POOL_DIR%
echo Check mode: %CHECK_ONLY%
echo Force dependency install: %FORCE_INSTALL%
echo Proxy deps install required: %INSTALL_PROXY_DEPS%
echo Port %PROXY_PORT% in use: %PROXY_PORT_IN_USE%
echo.

if "%CHECK_ONLY%"=="true" exit /b 0

if "%PROXY_PORT_IN_USE%"=="true" (
  echo Port %PROXY_PORT% is already in use. Proxy pool may already be running.
  exit /b 0
)

cd /d "%POOL_DIR%"

if not exist ".venv\Scripts\python.exe" (
  echo Creating venv for IPProxyPool...
  python -m venv .venv || exit /b 1
  set "INSTALL_PROXY_DEPS=true"
)

if "%INSTALL_PROXY_DEPS%"=="true" (
  echo Installing IPProxyPool dependencies...
  .venv\Scripts\python.exe -m pip install -r requirements.txt || exit /b 1
  if defined POOL_STAMP_VALUE (
    >"%POOL_STAMP_FILE%" echo(!POOL_STAMP_VALUE!
  )
) else (
  echo Proxy dependencies unchanged, skip install.
)

echo Starting IPProxyPool at http://127.0.0.1:%PROXY_PORT% ...
.venv\Scripts\python.exe IPProxy.py
exit /b 0

:is_port_listening
set "%~2=false"
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%~1 .*LISTENING"') do (
  set "%~2=true"
  goto :eof
)
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
if exist "%CANDIDATE%package.json" if exist "%CANDIDATE%third_party\IPProxyPool\IPProxy.py" (
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
  if not defined ROOT if exist "%%~fD\package.json" if exist "%%~fD\third_party\IPProxyPool\IPProxy.py" set "ROOT=%%~fD\"
  if not defined ROOT for /d %%S in ("%%~fD\*") do (
    if not defined ROOT if exist "%%~fS\package.json" if exist "%%~fS\third_party\IPProxyPool\IPProxy.py" set "ROOT=%%~fS\"
  )
)
exit /b 0

:root_not_found
echo Cannot locate project root. Set CARD_FLIP_ROOT first.
exit /b 1
