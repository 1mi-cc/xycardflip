[CmdletBinding()]
param(
  [ValidateSet("jd", "pinduoduo")]
  [string]$Provider,
  [string]$Keyword = "",
  [int]$Page = 1,
  [int]$Limit = 20,
  [int]$Port = 0,
  [Alias("Host")]
  [string]$ListenHost = "127.0.0.1",
  [int]$RemoteDebugPort = 9222,
  [int]$PageWaitMs = 6000,
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

function Resolve-ProviderScript {
  param([string]$ProviderName, [string]$ScriptRoot)

  switch ($ProviderName) {
    "jd" {
      return @{
        Script = (Join-Path $ScriptRoot "jd_browser_snapshot.py")
        DefaultPort = 8785
      }
    }
    "pinduoduo" {
      return @{
        Script = (Join-Path $ScriptRoot "pinduoduo_browser_snapshot.py")
        DefaultPort = 8786
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
  throw "Browser snapshot script not found: $targetScript"
}

$args = @(
  $targetScript,
  "--host", $ListenHost,
  "--port", $targetPort,
  "--page", $Page,
  "--limit", $Limit,
  "--remote-debug-port", $RemoteDebugPort,
  "--page-wait-ms", $PageWaitMs
)
if ($Keyword) {
  $args += @("--keyword", $Keyword)
}
if ($ReuseBrowser) {
  $args += "--reuse-browser"
}

Write-Host ("Starting {0} browser snapshot bridge on http://{1}:{2}" -f $Provider, $ListenHost, $targetPort) -ForegroundColor Cyan
& $pythonExe @args
exit $LASTEXITCODE
