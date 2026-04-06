param(
    [string]$ServerHost = "61.147.247.54",
    [int]$ServerPort = 18034,
    [string]$ServerUser = "root",
    [string]$RemoteAppRoot = "/srv/xycardflip",
    [string]$RemoteUploadRoot = "/tmp",
    [int]$PublicAppPort = 18036,
    [int]$KeepReleases = 5,
    [int]$ReleaseStorageBudgetMb = 768,
    [switch]$AllowDirty,
    [switch]$SkipBuild,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param(
        [string]$Description
    )

    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$releaseId = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
$archivePath = Join-Path $env:TEMP "xycardflip-release-$releaseId.tar.gz"
$remoteArchivePath = "$RemoteUploadRoot/xycardflip-release-$releaseId.tar.gz"
$remoteExtractPath = "$RemoteUploadRoot/xycardflip-release-$releaseId"
$sshTarget = "$ServerUser@$ServerHost"
$remoteServicePath = "$RemoteUploadRoot/xycardflip-backend.service"
$remoteNginxPath = "$RemoteUploadRoot/xycardflip.conf"
$remoteBootstrapPath = "$RemoteUploadRoot/server_bootstrap_release_base.sh"
$remoteSwitchPath = "$RemoteUploadRoot/server_switch_release.sh"
$remoteListPath = "$RemoteUploadRoot/server_list_releases.sh"
$remotePrunePath = "$RemoteUploadRoot/server_prune_releases.sh"
$remoteBackupScriptPath = "$RemoteUploadRoot/server_backup_backend_data.sh"
$remoteRestoreScriptPath = "$RemoteUploadRoot/server_restore_backend_from_backup.sh"
$remoteRehearsalScriptPath = "$RemoteUploadRoot/server_rehearse_backup_restore.sh"
$remoteBackupServicePath = "$RemoteUploadRoot/xycardflip-backup.service"
$remoteBackupTimerPath = "$RemoteUploadRoot/xycardflip-backup.timer"
$remoteRehearsalServicePath = "$RemoteUploadRoot/xycardflip-restore-rehearsal.service"
$remoteRehearsalTimerPath = "$RemoteUploadRoot/xycardflip-restore-rehearsal.timer"

Push-Location $repoRoot
try {
    if (-not $SkipTests) {
        Write-Host "Running backend tests..."
        python -m pytest backend\tests -q
        Assert-LastExitCode "Backend tests"
    }
    if (-not $SkipBuild) {
        Write-Host "Building frontend dist..."
        npm run build
        Assert-LastExitCode "Frontend build"
    }

    $branch = ((git rev-parse --abbrev-ref HEAD) | Out-String).Trim()
    Assert-LastExitCode "Resolve git branch"
    $commit = ((git rev-parse HEAD) | Out-String).Trim()
    Assert-LastExitCode "Resolve git commit"
    $statusOutput = ((git status --short) | Out-String).Trim()
    Assert-LastExitCode "Resolve git status"
    $dirty = if ($statusOutput) { "true" } else { "false" }
    if ($dirty -eq "true" -and -not $AllowDirty) {
        throw "Working tree is dirty. Commit/stash changes or rerun with -AllowDirty."
    }

    if (Test-Path $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }

    $distIndexPath = Join-Path $repoRoot "dist\\index.html"
    if (-not (Test-Path $distIndexPath)) {
        throw "Frontend dist is missing at $distIndexPath. Build first or remove -SkipBuild."
    }

    Write-Host "Packing release archive..."
    tar.exe `
        --exclude="backend/.venv" `
        --exclude="backend/.venv_pack" `
        --exclude="backend/data" `
        --exclude="backend/build" `
        --exclude="backend/dist" `
        -czf $archivePath `
        -C $repoRoot backend dist
    Assert-LastExitCode "Release archive packaging"

    Write-Host "Uploading release archive to server..."
    scp -P $ServerPort $archivePath "${sshTarget}:$remoteArchivePath"
    Assert-LastExitCode "Upload release archive"
    scp -P $ServerPort backend\deploy\systemd\xycardflip-backend.service "${sshTarget}:$remoteServicePath"
    Assert-LastExitCode "Upload backend service unit"
    scp -P $ServerPort backend\deploy\nginx\xycardflip.conf "${sshTarget}:$remoteNginxPath"
    Assert-LastExitCode "Upload nginx config"
    scp -P $ServerPort backend\scripts\server_bootstrap_release_base.sh "${sshTarget}:$remoteBootstrapPath"
    Assert-LastExitCode "Upload bootstrap script"
    scp -P $ServerPort backend\scripts\server_switch_release.sh "${sshTarget}:$remoteSwitchPath"
    Assert-LastExitCode "Upload switch script"
    scp -P $ServerPort backend\scripts\server_list_releases.sh "${sshTarget}:$remoteListPath"
    Assert-LastExitCode "Upload release list script"
    scp -P $ServerPort backend\scripts\server_prune_releases.sh "${sshTarget}:$remotePrunePath"
    Assert-LastExitCode "Upload release prune script"
    scp -P $ServerPort backend\scripts\server_backup_backend_data.sh "${sshTarget}:$remoteBackupScriptPath"
    Assert-LastExitCode "Upload backup script"
    scp -P $ServerPort backend\scripts\server_restore_backend_from_backup.sh "${sshTarget}:$remoteRestoreScriptPath"
    Assert-LastExitCode "Upload restore script"
    scp -P $ServerPort backend\scripts\server_rehearse_backup_restore.sh "${sshTarget}:$remoteRehearsalScriptPath"
    Assert-LastExitCode "Upload rehearsal script"
    scp -P $ServerPort backend\deploy\systemd\xycardflip-backup.service "${sshTarget}:$remoteBackupServicePath"
    Assert-LastExitCode "Upload backup service unit"
    scp -P $ServerPort backend\deploy\systemd\xycardflip-backup.timer "${sshTarget}:$remoteBackupTimerPath"
    Assert-LastExitCode "Upload backup timer unit"
    scp -P $ServerPort backend\deploy\systemd\xycardflip-restore-rehearsal.service "${sshTarget}:$remoteRehearsalServicePath"
    Assert-LastExitCode "Upload rehearsal service unit"
    scp -P $ServerPort backend\deploy\systemd\xycardflip-restore-rehearsal.timer "${sshTarget}:$remoteRehearsalTimerPath"
    Assert-LastExitCode "Upload rehearsal timer unit"

    $remoteCommand = @"
set -euo pipefail
install -m 644 '$remoteServicePath' /etc/systemd/system/xycardflip-backend.service
install -m 644 '$remoteBackupServicePath' /etc/systemd/system/xycardflip-backup.service
install -m 644 '$remoteBackupTimerPath' /etc/systemd/system/xycardflip-backup.timer
install -m 644 '$remoteRehearsalServicePath' /etc/systemd/system/xycardflip-restore-rehearsal.service
install -m 644 '$remoteRehearsalTimerPath' /etc/systemd/system/xycardflip-restore-rehearsal.timer
install -m 644 '$remoteNginxPath' /etc/nginx/sites-available/xycardflip.conf
rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/default.bak-*
ln -sfn /etc/nginx/sites-available/xycardflip.conf /etc/nginx/sites-enabled/xycardflip.conf
install -d /srv/xycardflip/bin
install -m 750 '$remoteBootstrapPath' /srv/xycardflip/bin/server_bootstrap_release_base.sh
install -m 750 '$remoteSwitchPath' /srv/xycardflip/bin/server_switch_release.sh
install -m 750 '$remoteListPath' /srv/xycardflip/bin/server_list_releases.sh
install -m 750 '$remotePrunePath' /srv/xycardflip/bin/server_prune_releases.sh
install -m 750 '$remoteBackupScriptPath' /srv/xycardflip/bin/server_backup_backend_data.sh
install -m 750 '$remoteRestoreScriptPath' /srv/xycardflip/bin/server_restore_backend_from_backup.sh
install -m 750 '$remoteRehearsalScriptPath' /srv/xycardflip/bin/server_rehearse_backup_restore.sh
rm -rf '$remoteExtractPath'
mkdir -p '$remoteExtractPath'
tar -xzf '$remoteArchivePath' -C '$remoteExtractPath'
APP_ROOT='$RemoteAppRoot' \
SOURCE_ROOT='$remoteExtractPath' \
SOURCE_LABEL='$repoRoot' \
SOURCE_BRANCH='$branch' \
SOURCE_COMMIT='$commit' \
SOURCE_DIRTY='$dirty' \
RELEASE_ID='$releaseId' \
/srv/xycardflip/bin/server_bootstrap_release_base.sh
/srv/xycardflip/bin/server_prune_releases.sh '$KeepReleases' '$ReleaseStorageBudgetMb'
systemctl daemon-reload
systemctl enable --now xycardflip-backup.timer
systemctl enable --now xycardflip-restore-rehearsal.timer
systemctl start xycardflip-backup.service
systemctl start xycardflip-restore-rehearsal.service
rm -rf '$remoteExtractPath'
rm -f '$remoteArchivePath'
rm -f '$remoteServicePath' '$remoteBackupServicePath' '$remoteBackupTimerPath' '$remoteRehearsalServicePath' '$remoteRehearsalTimerPath' '$remoteNginxPath' '$remoteBootstrapPath' '$remoteSwitchPath' '$remoteListPath' '$remotePrunePath' '$remoteBackupScriptPath' '$remoteRestoreScriptPath' '$remoteRehearsalScriptPath'
"@

    Write-Host "Applying release on server..."
    ssh -p $ServerPort $sshTarget $remoteCommand
    Assert-LastExitCode "Remote release apply"

    $publicBaseUrl = "http://${ServerHost}:${PublicAppPort}"
    $healthStatus = (curl.exe -s -o NUL -w "%{http_code}" "${publicBaseUrl}/health").Trim()
    Assert-LastExitCode "Public health request"
    $docsStatus = (curl.exe -s -o NUL -w "%{http_code}" "${publicBaseUrl}/docs").Trim()
    Assert-LastExitCode "Public docs request"
    $openApiStatus = (curl.exe -s -o NUL -w "%{http_code}" "${publicBaseUrl}/openapi.json").Trim()
    Assert-LastExitCode "Public OpenAPI request"

    if ($healthStatus -ne "200") {
        throw "Public health check failed with status $healthStatus at ${publicBaseUrl}/health"
    }
    if ($docsStatus -ne "403") {
        throw "Public docs check failed with status $docsStatus at ${publicBaseUrl}/docs"
    }
    if ($openApiStatus -ne "403") {
        throw "Public OpenAPI check failed with status $openApiStatus at ${publicBaseUrl}/openapi.json"
    }

    Write-Host "Release deployed."
    Write-Host "release_id=$releaseId"
    Write-Host "branch=$branch"
    Write-Host "commit=$commit"
    Write-Host "dirty=$dirty"
    Write-Host "allow_dirty=$AllowDirty"
    Write-Host "keep_releases=$KeepReleases"
    Write-Host "release_storage_budget_mb=$ReleaseStorageBudgetMb"
    Write-Host "public_health=$healthStatus"
    Write-Host "public_docs=$docsStatus"
    Write-Host "public_openapi=$openApiStatus"
}
finally {
    Pop-Location
    if (Test-Path $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
}
