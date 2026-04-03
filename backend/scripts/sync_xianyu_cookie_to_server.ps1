[CmdletBinding()]
param(
  [string]$ServerHost = "61.147.247.54",
  [int]$Port = 18034,
  [string]$User = "root",
  [string]$RemoteBackendDir = "/opt/xycardflip-main/backend",
  [switch]$KillBrowsers,
  [switch]$SkipMonitorStatus,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-PythonExecutable {
  param(
    [string]$BackendDir
  )

  $venvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
  if (Test-Path $venvPython) {
    return $venvPython
  }

  foreach ($candidate in @("python", "py")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
      return $candidate
    }
  }

  throw "Python executable not found. Create backend\.venv first or add python to PATH."
}

function Read-CookieFromEnv {
  param(
    [string]$EnvPath
  )

  if (-not (Test-Path $EnvPath)) {
    throw ".env not found: $EnvPath"
  }

  $line = Select-String -Path $EnvPath -Pattern '^XIAN_YU_COOKIE=' | Select-Object -First 1
  if (-not $line) {
    throw "XIAN_YU_COOKIE line not found in $EnvPath"
  }

  $cookie = ($line.Line -replace '^XIAN_YU_COOKIE=', '')
  if ([string]::IsNullOrWhiteSpace($cookie)) {
    throw "XIAN_YU_COOKIE is empty in $EnvPath"
  }
  if ($cookie -notmatch '_m_h5_tk=') {
    throw "Cookie is missing _m_h5_tk"
  }
  if ($cookie -notmatch '_m_h5_tk_enc=') {
    throw "Cookie is missing _m_h5_tk_enc"
  }

  return $cookie
}

function Write-Utf8File {
  param(
    [string]$Path,
    [string]$Content
  )

  $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$envPath = Join-Path $backendDir ".env"
$refreshScript = Join-Path $scriptDir "refresh_xianyu_cookie.py"

if (-not (Test-Path $refreshScript)) {
  throw "Refresh script not found: $refreshScript"
}

$pythonExe = Find-PythonExecutable -BackendDir $backendDir
$refreshArgs = @($refreshScript)
if ($KillBrowsers) {
  $refreshArgs += "--kill-browsers"
}

Write-Host "[1/4] Extracting fresh Xianyu cookie locally..." -ForegroundColor Cyan
& $pythonExe @refreshArgs
if ($LASTEXITCODE -ne 0) {
  throw "Cookie refresh script failed with exit code $LASTEXITCODE"
}

$cookie = Read-CookieFromEnv -EnvPath $envPath
Write-Host ("Cookie extracted successfully. Length={0}" -f $cookie.Length) -ForegroundColor Green

if ($DryRun) {
  Write-Host "DryRun enabled. Skipping upload." -ForegroundColor Yellow
  exit 0
}

$tempCookiePath = Join-Path $env:TEMP ("xycardflip-cookie-" + [guid]::NewGuid().ToString("N") + ".txt")
$tempRemoteScriptPath = Join-Path $env:TEMP ("xycardflip-sync-" + [guid]::NewGuid().ToString("N") + ".sh")
$remoteCookiePath = "$RemoteBackendDir/cookie-sync.txt"
$sshTarget = "$User@$ServerHost"

try {
  Write-Utf8File -Path $tempCookiePath -Content $cookie

  Write-Host "[2/4] Uploading cookie payload to server..." -ForegroundColor Cyan
  & scp -P $Port $tempCookiePath "${sshTarget}:$remoteCookiePath"
  if ($LASTEXITCODE -ne 0) {
    throw "scp upload failed with exit code $LASTEXITCODE"
  }

  $remoteScript = @"
set -e
python3 - <<'PY'
from pathlib import Path

env_path = Path(r"$RemoteBackendDir/.env")
cookie_path = Path(r"$remoteCookiePath")
cookie = cookie_path.read_text(encoding="utf-8")
lines = env_path.read_text(encoding="utf-8").splitlines()
updated = False

for i, line in enumerate(lines):
    if line.startswith("XIAN_YU_COOKIE="):
        lines[i] = "XIAN_YU_COOKIE=" + cookie
        updated = True
        break

if not updated:
    lines.append("XIAN_YU_COOKIE=" + cookie)

env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"cookie synced {len(cookie)}")
PY
"@

  if (-not $SkipMonitorStatus) {
    $remoteScript += @"
curl -s http://127.0.0.1:8000/monitor/status
"@
  }

  Write-Utf8File -Path $tempRemoteScriptPath -Content $remoteScript

  Write-Host "[3/4] Updating server-side backend .env..." -ForegroundColor Cyan
  Get-Content -Raw $tempRemoteScriptPath | & ssh -p $Port $sshTarget "bash -s"
  if ($LASTEXITCODE -ne 0) {
    throw "ssh remote update failed with exit code $LASTEXITCODE"
  }

  Write-Host "[4/4] Cookie sync complete." -ForegroundColor Green
} finally {
  Remove-Item $tempCookiePath -ErrorAction SilentlyContinue
  Remove-Item $tempRemoteScriptPath -ErrorAction SilentlyContinue
}
