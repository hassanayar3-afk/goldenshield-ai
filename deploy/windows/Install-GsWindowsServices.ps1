# Install GoldenShield as Windows Services (NSSM): API, bot daemon, cloudflared (when needed).
param(
    [string]$Root = "C:\GoldenShield_Binance",
    [switch]$RemoveScheduledTasks
)
$ErrorActionPreference = "Continue"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(544)
if (-not $isAdmin) {
    Write-Warning "WINDOWS_SERVICES_SKIP not elevated (Admin)"
    exit 2
}

Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root

$kill = Join-Path $Root "scripts\gs_kill_all.ps1"
if (Test-Path $kill) { & $kill -KillMobileApi }
Start-Sleep -Seconds 2

$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
$logDir = Join-Path $Root "storage\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$nssmDir = Join-Path $Root "tools\nssm"
$nssm = Join-Path $nssmDir "nssm.exe"
if (-not (Test-Path $nssm)) {
    New-Item -ItemType Directory -Force -Path $nssmDir | Out-Null
    $zip = Join-Path $env:TEMP "nssm-2.24.zip"
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $env:TEMP -Force
    $found = Get-ChildItem (Join-Path $env:TEMP "nssm-2.24") -Recurse -Filter "nssm.exe" |
        Where-Object { $_.FullName -match "win64" } | Select-Object -First 1
    if (-not $found) { throw "nssm.exe not found in zip" }
    Copy-Item $found.FullName $nssm -Force
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
}

function Install-GsService {
    param(
        [string]$Name,
        [string]$Exe,
        [string]$Args,
        [string]$StdoutLog,
        [string]$StderrLog
    )
    try { & $nssm stop $Name 2>$null | Out-Null } catch {}
    try { & $nssm remove $Name confirm 2>$null | Out-Null } catch {}
    & $nssm install $Name $Exe $Args | Out-Null
    & $nssm set $Name AppDirectory $Root | Out-Null
    & $nssm set $Name AppStdout $StdoutLog | Out-Null
    & $nssm set $Name AppStderr $StderrLog | Out-Null
    & $nssm set $Name AppRotateFiles 1 | Out-Null
    & $nssm set $Name AppRotateBytes 10485760 | Out-Null
    & $nssm set $Name Start SERVICE_AUTO_START | Out-Null
    & $nssm set $Name AppExit Default Restart | Out-Null
    & $nssm set $Name AppRestartDelay 5000 | Out-Null
    & $nssm start $Name | Out-Null
    Write-Host "SERVICE_OK $Name"
}

$psExe = (Get-Command powershell.exe).Source
$daemonScript = Join-Path $Root "gs_daemon.ps1"
$tunnelScript = Join-Path $PSScriptRoot "GS_TUNNEL_KEEPALIVE.ps1"

Install-GsService -Name "GoldenShieldMobileApi" `
    -Exe $py `
    -Args "-m terminal_app.server" `
    -StdoutLog (Join-Path $logDir "svc_mobile_api.log") `
    -StderrLog (Join-Path $logDir "svc_mobile_api.err.log")

Install-GsService -Name "GoldenShieldBotDaemon" `
    -Exe $psExe `
    -Args "-NoProfile -ExecutionPolicy Bypass -File `"$daemonScript`" -Root `"$Root`"" `
    -StdoutLog (Join-Path $logDir "svc_bot_daemon.log") `
    -StderrLog (Join-Path $logDir "svc_bot_daemon.err.log")

$staticUrl = $env:MOBILE_PUBLIC_BASE_URL -match "^https?://"
$namedToken = [bool]($env:CLOUDFLARE_TUNNEL_TOKEN -and $env:CLOUDFLARE_TUNNEL_TOKEN.Trim())
if ($staticUrl) {
    & (Join-Path $PSScriptRoot "START_CLOUDFLARE_TUNNEL.ps1") -Root $Root
    Write-Host "TUNNEL_STATIC_NO_CLOUDFLARED_SERVICE"
} elseif ($namedToken -or ($env:CLOUDFLARE_TUNNEL_ENABLED -ne "false")) {
    Install-GsService -Name "GoldenShieldCloudflareTunnel" `
        -Exe $psExe `
        -Args "-NoProfile -ExecutionPolicy Bypass -File `"$tunnelScript`" -Root `"$Root`"" `
        -StdoutLog (Join-Path $logDir "svc_tunnel.log") `
        -StderrLog (Join-Path $logDir "svc_tunnel.err.log")
}

if ($RemoveScheduledTasks) {
    foreach ($t in @("GoldenShieldDaemon", "GoldenShieldTunnel", "GoldenShieldWatchdog")) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Host "SCHEDULED_TASKS_REMOVED (services are primary)"
}

Write-Host "WINDOWS_SERVICES_INSTALLED"
exit 0
