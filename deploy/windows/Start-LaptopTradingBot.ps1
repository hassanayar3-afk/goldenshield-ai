# تشغيل main.py / gs_daemon على اللابتوب (نافذة مخفية)
param(
    [string]$Root = "",
    [switch]$UseDaemon
)
$ErrorActionPreference = "Continue"
if (-not $Root) {
    $Root = if ($env:GOLDENSHIELD_OFFICIAL_ROOT) { $env:GOLDENSHIELD_OFFICIAL_ROOT } else { (Get-Location).Path }
}
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
$env:PYTHONPATH = $Root
$py = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Run Setup-LaptopTradingBot.ps1 first" }

$runtime = Join-Path $Root "storage\runtime"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
Remove-Item (Join-Path $runtime "user_stopped.flag") -Force -ErrorAction SilentlyContinue

if ($UseDaemon -and (Test-Path (Join-Path $Root "gs_daemon.ps1"))) {
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        (Join-Path $Root "gs_daemon.ps1"), "-Root", $Root
    ) -WorkingDirectory $Root -WindowStyle Minimized
    Write-Host "STARTED gs_daemon.ps1"
} else {
    Start-Process -FilePath $py -ArgumentList @("main.py") -WorkingDirectory $Root -WindowStyle Minimized
    Write-Host "STARTED main.py"
}
Write-Host "Watch: storage\runtime\heartbeat.json and binance_snapshot.json"
