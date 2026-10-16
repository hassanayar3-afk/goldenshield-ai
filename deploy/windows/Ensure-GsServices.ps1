# GoldenShield — ensure persistent Mobile API, Discord sovereign bot, Cloudflare tunnel, watchdog
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root

Write-Host "=== Ensure-GsServices Root=$Root ==="

$regWatch = Join-Path $PSScriptRoot "REGISTER_GS_WATCHDOG.ps1"
if (Test-Path $regWatch) {
    try { & $regWatch -Root $Root } catch { Write-Warning $_.Exception.Message }
}

$ensureApi = Join-Path $PSScriptRoot "Ensure-GsMobileApi.ps1"
if (Test-Path $ensureApi) { & $ensureApi -Root $Root | Write-Host }

$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root

function Ensure-ProcessByPattern {
    param([string]$Pattern, [string]$LaunchArgs, [string]$Label)
    $n = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $Pattern
    }).Count
    if ($n -ge 1) {
        Write-Host "${Label}_OK count=$n"
        return
    }
    Start-Process -FilePath $py -ArgumentList $LaunchArgs -WorkingDirectory $Root -WindowStyle Hidden
    Write-Host "${Label}_STARTED"
}

$token = $(if ($env:DISCORD_BOT_TOKEN) { $env:DISCORD_BOT_TOKEN } else { "" }).Trim()
if ($token) {
    Ensure-ProcessByPattern -Pattern "gs_discord_bot\.py" -LaunchArgs @("$Root\gs_discord_bot.py") -Label "DISCORD_BOT"
} else {
    Write-Warning "DISCORD_BOT_TOKEN missing — skip gs_discord_bot.py"
}

Ensure-ProcessByPattern -Pattern "gs_snapshot_writer\.py" -LaunchArgs @("$Root\deploy_ops\gs_snapshot_writer.py") -Label "SNAPSHOT_WRITER"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(544)
$installSvc = Join-Path $PSScriptRoot "Install-GsWindowsServices.ps1"
if ($isAdmin -and (Test-Path $installSvc)) {
    try { & $installSvc -Root $Root } catch { Write-Warning $_.Exception.Message }
}

if ($env:CLOUDFLARE_TUNNEL_ENABLED -ne "false") {
    $cfTok = $(if ($env:CLOUDFLARE_TUNNEL_TOKEN) { $env:CLOUDFLARE_TUNNEL_TOKEN } else { "" }).Trim()
    if (-not $cfTok) {
        $tf = Join-Path $Root "storage\runtime\tunnel.token"
        if (Test-Path $tf) { $cfTok = (Get-Content $tf -Raw -Encoding ASCII).Trim() }
    }
    if ($cfTok) {
        & (Join-Path $PSScriptRoot "START_CLOUDFLARE_TUNNEL.ps1") -Root $Root
    } else {
        Write-Warning "CLOUDFLARE_TUNNEL_TOKEN missing"
    }
}

Start-Sleep -Seconds 2
try {
    $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 12
    Write-Host ("MOBILE_API_HEALTH ok=" + $h.ok)
} catch {
    Write-Host "MOBILE_API_HEALTH_FAIL"
}
Write-Host "ENSURE_GS_SERVICES_DONE"
