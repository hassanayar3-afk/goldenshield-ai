# One-shot: Mobile API service + watchdog + snapshot writer + tunnel (when token present)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root

Write-Host "=== Apply-SpinalFix Root=$Root ==="

$regWatch = Join-Path $PSScriptRoot "REGISTER_GS_WATCHDOG.ps1"
if (Test-Path $regWatch) {
    try { & $regWatch -Root $Root } catch { Write-Warning $_.Exception.Message }
}

$installSvc = Join-Path $PSScriptRoot "Install-GsWindowsServices.ps1"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(544)
if ($isAdmin -and (Test-Path $installSvc)) {
    try {
        & $installSvc -Root $Root
    } catch {
        Write-Warning ("INSTALL_SERVICES_FAIL " + $_.Exception.Message)
    }
} else {
    Write-Host "SERVICES_SKIP (not admin or script missing) — Ensure-GsMobileApi + daemon"
    & (Join-Path $PSScriptRoot "Ensure-GsMobileApi.ps1") -Root $Root
    $daemonTask = Get-ScheduledTask -TaskName "GoldenShieldDaemon" -ErrorAction SilentlyContinue
    if ($daemonTask -and $daemonTask.State -ne "Running") {
        Start-ScheduledTask -TaskName "GoldenShieldDaemon" -ErrorAction SilentlyContinue
    }
}

$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
$writer = Join-Path $Root "deploy_ops\gs_snapshot_writer.py"
if (Test-Path $writer) {
    $wRun = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match "gs_snapshot_writer\.py"
    }).Count
    if ($wRun -lt 1) {
        Start-Process -FilePath $py -ArgumentList @($writer) -WorkingDirectory $Root -WindowStyle Hidden
        Write-Host "SNAPSHOT_WRITER_STARTED"
    }
}

if ($env:CLOUDFLARE_TUNNEL_ENABLED -ne "false") {
    $tok = $(if ($env:CLOUDFLARE_TUNNEL_TOKEN) { $env:CLOUDFLARE_TUNNEL_TOKEN } else { "" }).Trim()
    if (-not $tok) {
        $tf = Join-Path $Root "storage\runtime\tunnel.token"
        if (Test-Path $tf) { $tok = (Get-Content $tf -Raw -Encoding ASCII).Trim() }
    }
    if ($tok) {
        & (Join-Path $PSScriptRoot "START_CLOUDFLARE_TUNNEL.ps1") -Root $Root
    } else {
        Write-Warning "CLOUDFLARE_TUNNEL_TOKEN missing — configure Zero Trust token in .env or storage\runtime\tunnel.token"
    }
}

Start-Sleep -Seconds 3
try {
    $h = Invoke-RestMethod "http://127.0.0.1:8790/api/health" -TimeoutSec 15
    Write-Host ("HEALTH ok=" + $h.ok)
    if ($h.spinal) { Write-Host ("SPINAL snapshot_age_sec=" + $h.spinal.snapshot_age_sec) }
} catch {
    Write-Host "HEALTH_FAIL"
}

$snap = Join-Path $Root "storage\runtime\binance_snapshot.json"
if (Test-Path $snap) {
    $age = [int]((Get-Date) - (Get-Item $snap).LastWriteTime).TotalSeconds
    Write-Host ("SNAPSHOT_AGE_SEC=" + $age)
}
Write-Host "APPLY_SPINAL_FIX_DONE"
