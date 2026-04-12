[CmdletBinding()]
param(
  [ValidateSet("xianyu", "jd", "pinduoduo")]
  [string]$Provider,
  [string]$ServerHost = "61.147.247.54",
  [int]$Port = 18034,
  [string]$User = "root",
  [string]$RemoteEnvPath = "/srv/xycardflip/shared/backend.env",
  [string]$RemoteReleaseEnvPath = "/srv/xycardflip/current/backend/.env",
  [switch]$KillBrowsers,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-PythonExecutable {
  param([string]$BackendDir)

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

function Get-ProviderMeta {
  param([string]$ProviderName)

  switch ($ProviderName) {
    "xianyu" {
      return @{
        EnvKey = "XIAN_YU_COOKIE"
        RefreshScript = "refresh_xianyu_cookie.py"
        RequiredPatterns = @("_m_h5_tk=", "_m_h5_tk_enc=")
      }
    }
    "jd" {
      return @{
        EnvKey = "JD_COOKIE"
        RefreshScript = "refresh_jd_cookie.py"
        RequiredPatterns = @()
      }
    }
    "pinduoduo" {
      return @{
        EnvKey = "PINDUODUO_COOKIE"
        RefreshScript = "refresh_pinduoduo_cookie.py"
        RequiredPatterns = @()
      }
    }
    default {
      throw "Unsupported provider: $ProviderName"
    }
  }
}

function Read-CookieFromEnv {
  param(
    [string]$EnvPath,
    [string]$EnvKey,
    [string[]]$RequiredPatterns
  )

  if (-not (Test-Path $EnvPath)) {
    throw ".env not found: $EnvPath"
  }

  $line = Select-String -Path $EnvPath -Pattern ('^{0}=' -f [regex]::Escape($EnvKey)) | Select-Object -First 1
  if (-not $line) {
    throw "$EnvKey line not found in $EnvPath"
  }

  $cookie = ($line.Line -replace ('^{0}=' -f [regex]::Escape($EnvKey)), '')
  if ([string]::IsNullOrWhiteSpace($cookie)) {
    throw "$EnvKey is empty in $EnvPath"
  }
  foreach ($pattern in $RequiredPatterns) {
    if ($cookie -notmatch [regex]::Escape($pattern)) {
      throw "Cookie is missing required token: $pattern"
    }
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

function Encode-Base64Utf8 {
  param([string]$Text)

  return [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Text))
}

$meta = Get-ProviderMeta -ProviderName $Provider
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$envPath = Join-Path $backendDir ".env"
$refreshScript = Join-Path $scriptDir $meta.RefreshScript

if (-not (Test-Path $refreshScript)) {
  throw "Refresh script not found: $refreshScript"
}

$pythonExe = Find-PythonExecutable -BackendDir $backendDir
$refreshArgs = @($refreshScript)
if ($KillBrowsers) {
  $refreshArgs += "--kill-browsers"
}

Write-Host ("[1/4] Extracting fresh {0} cookie locally..." -f $Provider) -ForegroundColor Cyan
& $pythonExe @refreshArgs
if ($LASTEXITCODE -ne 0) {
  throw "Cookie refresh script failed with exit code $LASTEXITCODE"
}

$cookie = Read-CookieFromEnv -EnvPath $envPath -EnvKey $meta.EnvKey -RequiredPatterns $meta.RequiredPatterns
Write-Host ("Cookie extracted successfully. Provider={0} Length={1}" -f $Provider, $cookie.Length) -ForegroundColor Green

if ($DryRun) {
  Write-Host "DryRun enabled. Skipping upload." -ForegroundColor Yellow
  exit 0
}

$tempCookiePath = Join-Path $env:TEMP ("marketplace-cookie-" + [guid]::NewGuid().ToString("N") + ".txt")
$tempRemoteScriptPath = Join-Path $env:TEMP ("marketplace-sync-" + [guid]::NewGuid().ToString("N") + ".sh")
$remoteCookiePath = "/tmp/cookie-sync-$Provider.txt"
$sshTarget = "$User@$ServerHost"

try {
  Write-Utf8File -Path $tempCookiePath -Content $cookie

  Write-Host "[2/4] Uploading cookie payload to server..." -ForegroundColor Cyan
  & scp -P $Port $tempCookiePath "${sshTarget}:$remoteCookiePath"
  if ($LASTEXITCODE -ne 0) {
    throw "scp upload failed with exit code $LASTEXITCODE"
  }

  $pythonCode = @"
from pathlib import Path; env_path = Path(r"$RemoteEnvPath"); release_env_path = Path(r"$RemoteReleaseEnvPath"); cookie_path = Path(r"$remoteCookiePath"); env_key = r"$($meta.EnvKey)"; cookie = cookie_path.read_text(encoding="utf-8"); raw_env = env_path.read_text(encoding="utf-8"); lines = raw_env.replace('\\n', chr(10)).splitlines(); idx = next((i for i, line in enumerate(lines) if line.startswith(env_key + '=')), -1); lines = (lines[:idx] + [env_key + '=' + cookie] + lines[idx + 1:]) if idx >= 0 else (lines + [env_key + '=' + cookie]); env_path.write_text(chr(10).join(lines) + chr(10), encoding='utf-8'); (release_env_path.unlink() if release_env_path.exists() and not release_env_path.is_symlink() else None); (release_env_path.symlink_to(env_path) if not release_env_path.exists() else None); print(f'cookie synced {env_key} {len(cookie)}')
"@ -replace "`r`n", "`n"
  $pythonCodeBase64 = Encode-Base64Utf8 -Text $pythonCode
  $remoteScript = "set -e`npython3 -c `"import base64; exec(base64.b64decode('$pythonCodeBase64').decode('utf-8'))`""

  $remoteScript = $remoteScript -replace "`r`n", "`n"
  Write-Utf8File -Path $tempRemoteScriptPath -Content $remoteScript

  Write-Host "[3/4] Updating server-side backend .env..." -ForegroundColor Cyan
  Get-Content -Raw $tempRemoteScriptPath | & ssh -p $Port $sshTarget "bash -s"
  if ($LASTEXITCODE -ne 0) {
    throw "ssh remote update failed with exit code $LASTEXITCODE"
  }

  Write-Host ("[4/4] Cookie sync complete for {0}." -f $Provider) -ForegroundColor Green
} finally {
  Remove-Item $tempCookiePath -ErrorAction SilentlyContinue
  Remove-Item $tempRemoteScriptPath -ErrorAction SilentlyContinue
}
