[CmdletBinding()]
param(
  [ValidateSet("jd", "pinduoduo")]
  [string]$Provider,
  [string]$Keyword = "Pokemon Card PSA 10",
  [int]$RemoteDebugPort = 0,
  [string]$ProfileDirectory = "Default",
  [switch]$ReuseIfRunning,
  [switch]$CheckOnly
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

  throw "Python executable not found. Create backend\\.venv first or add python to PATH."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$pythonExe = Find-PythonExecutable -BackendDir $backendDir
$targetScript = Join-Path $scriptDir "browser_session_keeper.py"

if (-not (Test-Path $targetScript)) {
  throw "Session keeper script not found: $targetScript"
}

$args = @(
  $targetScript,
  "--provider", $Provider,
  "--keyword", $Keyword,
  "--profile-directory", $ProfileDirectory
)
if ($RemoteDebugPort -gt 0) {
  $args += @("--remote-debug-port", $RemoteDebugPort)
}
if ($ReuseIfRunning) {
  $args += "--reuse-if-running"
}
if ($CheckOnly) {
  $args += "--check-only"
}

Write-Host ("Starting browser session keeper for {0}..." -f $Provider) -ForegroundColor Cyan
& $pythonExe @args
exit $LASTEXITCODE
