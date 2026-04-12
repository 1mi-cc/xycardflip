[CmdletBinding()]
param(
  [ValidateSet("jd", "pinduoduo")]
  [string]$Provider,
  [int]$WatchSeconds = 25,
  [int]$MaxResults = 20,
  [switch]$ReuseBrowser
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

function Resolve-CaptureScript {
  param([string]$ProviderName, [string]$ScriptRoot)

  switch ($ProviderName) {
    "jd" { return Join-Path $ScriptRoot "capture_jd_upstream.py" }
    "pinduoduo" { return Join-Path $ScriptRoot "capture_pinduoduo_upstream.py" }
    default { throw "Unsupported provider: $ProviderName" }
  }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$pythonExe = Find-PythonExecutable -BackendDir $backendDir
$targetScript = Resolve-CaptureScript -ProviderName $Provider -ScriptRoot $scriptDir

if (-not (Test-Path $targetScript)) {
  throw "Capture script not found: $targetScript"
}

$args = @(
  $targetScript,
  "--watch-seconds", $WatchSeconds,
  "--max-results", $MaxResults
)
if ($ReuseBrowser) {
  $args += "--reuse-browser"
}

Write-Host ("Starting upstream capture for {0}. Watch window={1}s" -f $Provider, $WatchSeconds) -ForegroundColor Cyan
Write-Host "Use the opened browser page to search products during the watch window." -ForegroundColor Yellow
& $pythonExe @args
exit $LASTEXITCODE
