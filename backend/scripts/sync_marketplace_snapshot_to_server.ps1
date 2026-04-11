[CmdletBinding()]
param(
  [ValidateSet("jd", "pinduoduo")]
  [string]$Provider,
  [string]$BridgeUrl,
  [string]$ServerHost = "61.147.247.54",
  [int]$PublicAppPort = 18036,
  [string]$Username = "",
  [string]$Password = "",
  [int]$Limit = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-DefaultBridgeUrl {
  param([string]$ProviderName)

  switch ($ProviderName) {
    "jd" { return "http://127.0.0.1:8785/snapshot" }
    "pinduoduo" { return "http://127.0.0.1:8786/snapshot" }
    default { throw "Unsupported provider: $ProviderName" }
  }
}

function Resolve-AuthValue {
  param(
    [string]$Explicit,
    [string]$EnvKey,
    [string]$Fallback
  )
  if ($Explicit) { return $Explicit }
  $envValue = [Environment]::GetEnvironmentVariable($EnvKey)
  if ($envValue) { return $envValue }
  return $Fallback
}

$baseUrl = "http://${ServerHost}:${PublicAppPort}/card-api"
$targetBridgeUrl = if ($BridgeUrl) { $BridgeUrl } else { Resolve-DefaultBridgeUrl -ProviderName $Provider }
$resolvedUsername = Resolve-AuthValue -Explicit $Username -EnvKey "CARD_FLIP_USERNAME" -Fallback "operator"
$resolvedPassword = Resolve-AuthValue -Explicit $Password -EnvKey "CARD_FLIP_PASSWORD" -Fallback "Ccj666888.qwer1013"

Write-Host ("Fetching snapshot from {0}..." -f $targetBridgeUrl) -ForegroundColor Cyan
$snapshot = Invoke-RestMethod -UseBasicParsing -Method Get -Uri "${targetBridgeUrl}?limit=${Limit}"
if ($snapshot.ready_for_push -ne $true) {
  $acceptedCount = [int]($snapshot.accepted_item_count | ForEach-Object { $_ })
  $pageState = [string]($snapshot.page_state | ForEach-Object { $_ })
  throw ("Snapshot is not ready for push. page_state={0} accepted_item_count={1}" -f $pageState, $acceptedCount)
}

$loginBody = @{ username = $resolvedUsername; password = $resolvedPassword } | ConvertTo-Json
$login = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "${baseUrl}/auth/login" -ContentType "application/json" -Body $loginBody
$token = $login.data.token
if (-not $token) {
  throw "Remote auth token missing."
}
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }

switch ($Provider) {
  "jd" {
    $payload = ($snapshot.payload | ConvertTo-Json -Depth 20 -Compress)
    $result = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "${baseUrl}/marketplace/providers/jd/ingest-snapshot" -Headers $headers -Body $payload
  }
  "pinduoduo" {
    $payload = ($snapshot.payload | ConvertTo-Json -Depth 20 -Compress)
    $result = Invoke-RestMethod -UseBasicParsing -Method Post -Uri "${baseUrl}/marketplace/providers/pinduoduo/ingest-snapshot" -Headers $headers -Body $payload
  }
  default {
    throw "Unsupported provider: $Provider"
  }
}

Write-Host ("Pushed {0} snapshot to server. inserted={1}" -f $Provider, ($result.inserted | ForEach-Object { $_ })) -ForegroundColor Green
$result | ConvertTo-Json -Depth 10
