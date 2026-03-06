@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PYTHON_PACK=%ROOT%backend\.venv_pack\Scripts\python.exe"
set "RELEASE_DIR=release"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "BUILD_STAMP=%%I"
if not defined BUILD_STAMP set "BUILD_STAMP=manual"
set "APP_DIR=%RELEASE_DIR%\CardFlipAssistant_%BUILD_STAMP%"
set "ZIP_PATH=%RELEASE_DIR%\CardFlipAssistant_Windows_%BUILD_STAMP%.zip"

echo [1/6] Building frontend...
call npm run build
if errorlevel 1 goto :fail

echo [2/6] Preparing packaging virtual env...
if not exist "%PYTHON_PACK%" (
  py -3 -m venv "backend\.venv_pack"
  if errorlevel 1 goto :fail
)

echo [3/6] Installing packaging dependencies...
call "%PYTHON_PACK%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
call "%PYTHON_PACK%" -m pip install -r "backend\requirements.txt" pyinstaller
if errorlevel 1 goto :fail

echo [4/6] Building executable...
pushd "backend"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist CardFlipAssistant.spec del /f /q CardFlipAssistant.spec
call "%PYTHON_PACK%" -m PyInstaller --noconfirm --clean --name CardFlipAssistant --onedir --hidden-import browser_cookie3 --hidden-import websocket --add-data "..\dist;frontend_dist" --add-data "scripts;scripts" app\desktop_main.py
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo [5/6] Assembling release folder...
if not exist "%RELEASE_DIR%" mkdir "%RELEASE_DIR%"
if exist "%APP_DIR%" rmdir /s /q "%APP_DIR%"
mkdir "%APP_DIR%"
robocopy "backend\dist\CardFlipAssistant" "%APP_DIR%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

set "ENV_SOURCE=backend\.env"
if not exist "%ENV_SOURCE%" set "ENV_SOURCE=backend\.env.example"
copy /Y "%ENV_SOURCE%" "%APP_DIR%\.env" >nul
powershell -NoProfile -Command ^
  "$path='%APP_DIR%\.env';" ^
  "$source='%ENV_SOURCE%';" ^
  "$lines=Get-Content -LiteralPath $path -Encoding UTF8;" ^
  "$lines=$lines | Where-Object {$_ -notmatch '^API_HOST=' -and $_ -notmatch '^SQLITE_PATH='};" ^
  "$defaults=@{RAGFLOW_ENABLED='false';RAGFLOW_BASE_URL='http://127.0.0.1:9380';RAGFLOW_API_KEY='';RAGFLOW_CHAT_ID='';RAGFLOW_TIMEOUT_SEC='45'};" ^
  "foreach($k in $defaults.Keys){ if(-not ($lines -match ('^' + [regex]::Escape($k) + '='))){ $lines += ($k + '=' + $defaults[$k]) } };" ^
  "$authKeys=@('UI_AUTH_USERNAME','UI_AUTH_PASSWORD','UI_AUTH_NICKNAME','UI_AUTH_DEFAULT_ROLE','UI_AUTH_SESSION_HOURS','UI_AUTH_ALLOW_REGISTRATION');" ^
  "$sourceMap=@{};" ^
  "if(Test-Path -LiteralPath $source){ foreach($raw in (Get-Content -LiteralPath $source -Encoding UTF8)){ if($raw -match '^(?<key>[A-Z0-9_]+)=(?<value>.*)$'){ $sourceMap[$matches['key']]=$matches['value'] } } };" ^
  "$lines=$lines | Where-Object { $keep=$true; foreach($k in $authKeys){ if($_ -match ('^' + [regex]::Escape($k) + '=')){ $keep=$false; break } }; $keep };" ^
  "foreach($k in $authKeys){ if($sourceMap.ContainsKey($k)){ $lines += ($k + '=' + $sourceMap[$k]) } };" ^
  "$lines += 'API_HOST=127.0.0.1';" ^
  "$lines += 'SQLITE_PATH=./data/trading.db';" ^
  "Set-Content -LiteralPath $path -Value $lines -Encoding UTF8"

if exist "%APP_DIR%\data" (
  del /f /q "%APP_DIR%\data\*.db" >nul 2>nul
) else (
  mkdir "%APP_DIR%\data"
)
powershell -NoProfile -Command ^
  "Get-ChildItem -LiteralPath '%APP_DIR%' -Recurse -File | Where-Object { $_.Extension -ieq '.db' -or $_.Name -ieq 'database.db' -or $_.Name -ieq 'trading.db' } | Remove-Item -Force -ErrorAction SilentlyContinue"

copy /Y "start_card_flip_app.template.bat" "%RELEASE_DIR%\start_card_flip_app.bat" >nul
if errorlevel 1 goto :fail

echo [6/6] Creating zip package...
powershell -NoProfile -Command ^
  "Compress-Archive -Path '%APP_DIR%','%RELEASE_DIR%\start_card_flip_app.bat' -DestinationPath '%ZIP_PATH%' -Force"

echo.
echo Packaging completed.
echo Folder: %APP_DIR%
echo Starter: %RELEASE_DIR%\start_card_flip_app.bat
echo Zip: %ZIP_PATH%
exit /b 0

:fail
echo.
echo Packaging failed. Please check logs above.
exit /b 1
