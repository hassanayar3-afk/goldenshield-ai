# GoldenShield Terminal — تشغيل إنتاج متكامل (24/7 + API + Tri-Commander + Discord + Tunnel)
param(
    [string]$Root = "",
    [switch]$SkipKillMobileApi,
    [switch]$RestartMobileApi
)
$ErrorActionPreference = "Continue"
if (-not $Root) {
    $Root = if ($env:GOLDENSHIELD_OFFICIAL_ROOT) { $env:GOLDENSHIELD_OFFICIAL_ROOT } else { "C:\GoldenShield_Binance" }
}
if (-not (Test-Path (Join-Path $Root "main.py"))) {
    throw "main.py not found under $Root"
}
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
if ($env:CLOUDFLARE_TUNNEL_ENABLED -ne "false" -and $env:CLOUDFLARE_TUNNEL_ENABLED -ne "0") {
    $env:CLOUDFLARE_TUNNEL_ENABLED = "true"
}

Write-Host "=== GS_START_FULL_STACK Root=$Root ==="

$aclFix = Join-Path $PSScriptRoot "Fix-GsRuntimeAcl.ps1"
if (Test-Path $aclFix) { & $aclFix -Root $Root }

& (Join-Path $PSScriptRoot "ENFORCE_NO_SLEEP.ps1") -RegisterTask
& (Join-Path $PSScriptRoot "ENFORCE_NO_SLEEP.ps1")
Start-Process powershell -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $PSScriptRoot "ENFORCE_NO_SLEEP.ps1"), "-Loop"
) -WindowStyle Minimized

$runtime = Join-Path $Root "storage\runtime"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
Remove-Item (Join-Path $runtime "user_stopped.flag") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $runtime "bot_instance.lock") -Force -ErrorAction SilentlyContinue
Remove-Item "C:\ProgramData\GoldenShield\bot_instance.lock" -Force -ErrorAction SilentlyContinue

Stop-ScheduledTask -TaskName "GoldenShieldDaemon" -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName "GoldenShieldTunnel" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$kill = Join-Path $Root "scripts\gs_kill_all.ps1"
if (Test-Path $kill) {
    $killArgs = @()
    if ($RestartMobileApi) { $killArgs += "-KillMobileApi" }
    elseif ($SkipKillMobileApi) { /* preserve API */ }
    else { $killArgs += "-KillMobileApi" }
    & $kill @killArgs
}
Start-Sleep -Seconds 2

$ensureApi = Join-Path $PSScriptRoot "Ensure-GsMobileApi.ps1"
if (Test-Path $ensureApi) {
    & $ensureApi -Root $Root | Write-Host
} else {
    $pyApi = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
    Start-Process -FilePath $pyApi -ArgumentList @("-m", "terminal_app.server") `
        -WorkingDirectory $Root -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

& (Join-Path $PSScriptRoot "START_CLOUDFLARE_TUNNEL.ps1") -Root $Root
Start-Sleep -Seconds 2
& (Join-Path $PSScriptRoot "START_DISCORD_BRIDGE.ps1") -Root $Root

$regTunnel = Join-Path $PSScriptRoot "REGISTER_GS_TUNNEL_TASK.ps1"
if (Test-Path $regTunnel) {
    try { & $regTunnel -Root $Root } catch { Write-Warning $_.Exception.Message }
}

# Prefer long-lived Scheduled Task daemon (survives WinRM / short parent exit)
$regDaemon = Join-Path $PSScriptRoot "REGISTER_GS_DAEMON_TASK.ps1"
if (Test-Path $regDaemon) {
    try {
        & $regDaemon -Root $Root
    } catch {
        Start-Process powershell -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            (Join-Path $Root "gs_daemon.ps1"), "-Root", $Root
        ) -WorkingDirectory $Root -WindowStyle Hidden
    }
} else {
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        (Join-Path $Root "gs_daemon.ps1"), "-Root", $Root
    ) -WorkingDirectory $Root -WindowStyle Hidden
}

$tun = ""
$tunFile = Join-Path $runtime "mobile_tunnel_url.txt"
if (Test-Path $tunFile) { $tun = (Get-Content $tunFile -Raw).Trim() }

$stack = @{
    ts = (Get-Date).ToUniversalTime().ToString("o")
    tunnel_url = $tun
    mobile_api_port = $(if ($env:MOBILE_API_PORT) { $env:MOBILE_API_PORT } else { "8790" })
    terminal_ws_port = $(if ($env:TERMINAL_WS_PORT) { $env:TERMINAL_WS_PORT } else { "8791" })
    tri_commander = ($env:TRI_COMMANDER_MODE -ne "false")
    discord_enabled = ($env:DISCORD_NOTIFY_ENABLED -ne "false")
    starter = "GS_START_FULL_STACK.bat"
}
$stack | ConvertTo-Json | Set-Content (Join-Path $runtime "gs_stack_status.json") -Encoding UTF8

Write-Host "STACK_OK local=http://127.0.0.1:$($env:MOBILE_API_PORT)/ tunnel=$tun"
Write-Host "STOP: STOP_BOT_FULL.bat"
