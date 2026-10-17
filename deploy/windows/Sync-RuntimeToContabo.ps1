# مزامنة مستمرة: storage/runtime من اللابتوب → Contabo (كل 15 ث افتراضياً)
param(
    [string]$Root = "",
    [int]$IntervalSec = 0,
    [switch]$IncludeDb
)
$ErrorActionPreference = "Continue"
if (-not $Root) {
    $Root = if ($env:GOLDENSHIELD_OFFICIAL_ROOT) { $env:GOLDENSHIELD_OFFICIAL_ROOT } else { (Get-Location).Path }
}
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
if ($IntervalSec -le 0) {
    $IntervalSec = [int]($(if ($env:RUNTIME_SYNC_INTERVAL_SEC) { $env:RUNTIME_SYNC_INTERVAL_SEC } else { "15" }))
}
$py = Join-Path $Root "venv\Scripts\python.exe"
$sync = Join-Path $Root "scripts\sync_runtime_to_contabo.py"
if (-not (Test-Path $py)) { throw "venv missing — run Setup-LaptopTradingBot.ps1" }

Write-Host "=== Sync-RuntimeToContabo interval=${IntervalSec}s root=$Root ==="
while ($true) {
    $args = @($sync)
    if ($IncludeDb) { $args += "--include-db" }
    & $py @args 2>&1 | ForEach-Object { Write-Host $_ }
    Start-Sleep -Seconds $IntervalSec
}
