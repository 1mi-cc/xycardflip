[CmdletBinding()]
param(
  [ValidateSet("xianyu", "jd", "pinduoduo")]
  [string]$Provider = "xianyu",
  [string]$ServerHost = "61.147.247.54",
  [int]$Port = 18034,
  [string]$User = "root",
  [int]$PublicAppPort = 18036,
  [int]$IntervalMinutes = 20,
  [switch]$KillBrowsers,
  [ValidateSet("none", "run-once", "start")]
  [string]$RemoteAction = "none"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$syncScript = Join-Path $scriptDir "sync_marketplace_cookie_to_server.ps1"

if (-not (Test-Path $syncScript)) {
  throw "Sync script not found: $syncScript"
}

function Invoke-CookieSync {
  $syncArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $syncScript,
    "-Provider", $Provider,
    "-ServerHost", $ServerHost,
    "-Port", $Port,
    "-User", $User
  )
  if ($KillBrowsers) {
    $syncArgs += "-KillBrowsers"
  }

  & powershell @syncArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Cookie sync failed with exit code $LASTEXITCODE"
  }
}

function Invoke-RemoteAction {
  param(
    [string]$ActionMode
  )

  if ($ActionMode -eq "none") {
    return
  }
  if ($Provider -ne "xianyu") {
    Write-Host ("Skipping remote action for provider={0}. Only xianyu bridge can trigger monitor actions." -f $Provider) -ForegroundColor Yellow
    return
  }

  $sshTarget = "$User@$ServerHost"
  $credsText = & ssh -p $Port $sshTarget "grep -E '^UI_AUTH_(USERNAME|PASSWORD)=' /srv/xycardflip/current/backend/.env || true"
  if ($LASTEXITCODE -ne 0) {
    throw "Remote credential read failed with exit code $LASTEXITCODE"
  }

  $usernameLine = ($credsText | Select-String -Pattern '^UI_AUTH_USERNAME=' | Select-Object -First 1)
  $passwordLine = ($credsText | Select-String -Pattern '^UI_AUTH_PASSWORD=' | Select-Object -First 1)
  $username = if ($usernameLine) { ($usernameLine.Line -replace '^UI_AUTH_USERNAME=', '').Trim() } else { '' }
  $password = if ($passwordLine) { ($passwordLine.Line -replace '^UI_AUTH_PASSWORD=', '').Trim() } else { '' }
  if (-not $username -or -not $password) {
    throw "Remote auth credentials missing."
  }

  $baseUrl = "http://${ServerHost}:${PublicAppPort}/card-api"
  $loginBody = @{ username = $username; password = $password } | ConvertTo-Json
  $login = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "${baseUrl}/auth/login" -ContentType "application/json" -Body $loginBody
  $token = $login.data.token
  if (-not $token) {
    throw "Remote action auth token missing."
  }
  $headers = @{ Authorization = "Bearer $token" }

  $null = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "${baseUrl}/monitor/reset-circuit?reason=cookie-bridge" -Headers $headers

  if ($ActionMode -eq "run-once") {
    $result = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "${baseUrl}/monitor/run-once" -Headers $headers
  }
  else {
    $result = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "${baseUrl}/monitor/start" -Headers $headers
  }

  Write-Output ($result | ConvertTo-Json -Compress -Depth 6)
}

Write-Host ("Cookie bridge started. provider={0} interval={1}m remote_action={2}" -f $Provider, $IntervalMinutes, $RemoteAction) -ForegroundColor Cyan

while ($true) {
  $startedAt = Get-Date
  try {
    Write-Host ("[{0}] Syncing {1} cookie to server..." -f $startedAt.ToString("yyyy-MM-dd HH:mm:ss"), $Provider) -ForegroundColor Cyan
    Invoke-CookieSync
    Invoke-RemoteAction -ActionMode $RemoteAction
    Write-Host ("[{0}] Cookie bridge cycle completed for {1}." -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Provider) -ForegroundColor Green
  } catch {
    Write-Host ("[{0}] Cookie bridge cycle failed for {1}: {2}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Provider, $_.Exception.Message) -ForegroundColor Yellow
  }

  Start-Sleep -Seconds ([Math]::Max(60, $IntervalMinutes * 60))
}
