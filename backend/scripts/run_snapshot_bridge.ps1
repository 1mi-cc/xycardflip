[CmdletBinding()]
param(
  [ValidateSet("jd", "pinduoduo")]
  [string]$Provider,
  [string]$SourceUrl,
  [ValidateSet("GET", "POST")]
  [string]$UpstreamMethod = "GET",
  [int]$Port = 0,
  [string]$Host = "127.0.0.1",
  [string]$ParamsJson = "",
  [string]$BodyJson = ""
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

function Resolve-ProviderScript {
  param([string]$ProviderName, [string]$ScriptRoot)

  switch ($ProviderName) {
    "jd" {
      return @{
        Script = (Join-Path $ScriptRoot "jd_snapshot_bridge.py")
        DefaultPort = 8765
      }
    }
    "pinduoduo" {
      return @{
        Script = (Join-Path $ScriptRoot "pinduoduo_snapshot_bridge.py")
        DefaultPort = 8766
      }
    }
    default {
      throw "Unsupported provider: $ProviderName"
    }
  }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$pythonExe = Find-PythonExecutable -BackendDir $backendDir
$providerMeta = Resolve-ProviderScript -ProviderName $Provider -ScriptRoot $scriptDir
$targetScript = $providerMeta.Script
$targetPort = if ($Port -gt 0) { $Port } else { [int]$providerMeta.DefaultPort }

if (-not (Test-Path $targetScript)) {
  throw "Bridge script not found: $targetScript"
}
if (-not $SourceUrl) {
  throw "SourceUrl is required."
}

$args = @(
  $targetScript,
  "--host", $Host,
  "--port", $targetPort,
  "--source-url", $SourceUrl,
  "--upstream-method", $UpstreamMethod
)
if ($ParamsJson) {
  $args += @("--params-json", $ParamsJson)
}
if ($BodyJson) {
  $args += @("--body-json", $BodyJson)
}

Write-Host ("Starting {0} snapshot bridge on http://{1}:{2}" -f $Provider, $Host, $targetPort) -ForegroundColor Cyan
& $pythonExe @args
exit $LASTEXITCODE
