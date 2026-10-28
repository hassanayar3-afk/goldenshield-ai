<#
.SYNOPSIS
  GoldenShield — تشغيل كامل على اللابتوب (بوت + مزامنة Contabo) بضغطة واحدة.

.DESCRIPTION
  1) venv + pip install -r requirements.txt
  2) التحقق من .env (Binance Demo + WIN_* للمزامنة)
  3) test_binance_connection.py
  4) gs_daemon / main.py
  5) مزامنة runtime كل 15 ث (نافذة منفصلة)

  Contabo: شغّل GOLDENSHIELD_CONTABO_PANEL_ONE_SHOT.ps1 على السيرفر أولاً.
#>
param(
    [string]$Root = "",
    [switch]$SkipSyncWindow,
    [int]$WaitHeartbeatSec = 90
)
$ErrorActionPreference = "Continue"
$scriptDir = $PSScriptRoot
if (-not $Root) {
    $Root = if ($env:GOLDENSHIELD_OFFICIAL_ROOT) { $env:GOLDENSHIELD_OFFICIAL_ROOT } else {
        (Resolve-Path (Join-Path $scriptDir "..\..")).Path
    }
}
Set-Location $Root
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " GoldenShield LAPTOP ONE-SHOT" -ForegroundColor Cyan
Write-Host " Root=$Root" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# --- 1) venv + requirements ---
$venvPy = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "[1/6] Creating venv..."
    $sysPy = (Get-Command python -ErrorAction Stop).Source
    & $sysPy -m venv (Join-Path $Root "venv")
    $venvPy = Join-Path $Root "venv\Scripts\python.exe"
} else {
    Write-Host "[1/6] venv exists"
}
& $venvPy -m pip install --upgrade pip --quiet
Write-Host "[1/6] Installing requirements.txt (may take a few minutes)..."
& $venvPy -m pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed" -ForegroundColor Red
    exit 1
}

# --- 2) .env ---
Write-Host "[2/6] Checking .env..."
. (Join-Path $scriptDir "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$skipSyncCheck = ($env:GS_SKIP_RUNTIME_SYNC -eq "true")
& (Join-Path $scriptDir "Ensure-LaptopEnv.ps1") -Root $Root -SkipContaboSyncCheck:$skipSyncCheck
if ($LASTEXITCODE -ne 0) {
    notepad (Join-Path $Root ".env") 2>$null
    exit $LASTEXITCODE
}
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
$env:PYTHONPATH = $Root

# --- 3) Binance test ---
Write-Host "[3/6] Binance connection test..."
& $venvPy (Join-Path $Root "scripts\test_binance_connection.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Binance test FAILED (451? proxy? keys?) — fix .env and retry" -ForegroundColor Red
    exit 1
}
Write-Host "[3/6] Binance OK" -ForegroundColor Green

# --- 4) Start bot ---
Write-Host "[4/6] Starting trading bot (daemon)..."
$runtime = Join-Path $Root "storage\runtime"
$logs = Join-Path $Root "storage\logs"
New-Item -ItemType Directory -Force -Path $runtime, $logs | Out-Null
Remove-Item (Join-Path $runtime "user_stopped.flag") -Force -ErrorAction SilentlyContinue

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and ($_.CommandLine -match "main\.py" -or $_.CommandLine -match "gs_daemon\.ps1")
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$daemon = Join-Path $Root "gs_daemon.ps1"
if (Test-Path $daemon) {
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $daemon, "-Root", $Root
    ) -WorkingDirectory $Root -WindowStyle Minimized
} else {
    Start-Process -FilePath $venvPy -ArgumentList @("main.py") -WorkingDirectory $Root -WindowStyle Minimized
}

# --- 5) Wait for runtime files ---
Write-Host "[5/6] Waiting for heartbeat (max ${WaitHeartbeatSec}s)..."
$hb = Join-Path $runtime "heartbeat.json"
$snap = Join-Path $runtime "binance_snapshot.json"
$deadline = (Get-Date).AddSeconds($WaitHeartbeatSec)
while ((Get-Date) -lt $deadline) {
    if ((Test-Path $hb) -and (Test-Path $snap)) { break }
    Start-Sleep -Seconds 3
}
if (-not (Test-Path $hb)) {
    Write-Warning "heartbeat.json not found yet — check storage\logs\gs_daemon.log"
} else {
    Write-Host "[5/6] Runtime files present" -ForegroundColor Green
}

# --- 6) Sync ---
Write-Host "[6/6] First sync to Contabo..."
& $venvPy (Join-Path $Root "scripts\sync_runtime_to_contabo.py")
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Sync failed — open SSH port 22 on Contabo or set WIN_SSH_PRIVATE_KEY in .env"
} else {
    Write-Host "[6/6] Sync OK" -ForegroundColor Green
}

if (-not $SkipSyncWindow) {
    Write-Host "Opening continuous sync window (every 15s) — keep it open while trading" -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File",
        (Join-Path $scriptDir "Sync-RuntimeToContabo.ps1"), "-Root", $Root
    ) -WorkingDirectory $Root
}

Write-Host ""
Write-Host "DONE — Bot running locally. Panel on Contabo updates via sync." -ForegroundColor Green
Write-Host "Logs: storage\logs\gs_daemon.log"
Write-Host "Stop bot: create storage\runtime\user_stopped.flag or close daemon process"
exit 0
