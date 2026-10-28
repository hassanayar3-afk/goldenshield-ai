param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")

$enabled = ($env:DISCORD_NOTIFY_ENABLED -ne "false") -and ($env:DISCORD_NOTIFY_ENABLED -ne "0")
if (-not $enabled) {
    Write-Host "DISCORD_BRIDGE_DISABLED"
    exit 0
}

$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
$script = Join-Path $Root "bridges\discord\discord_bridge.py"
if (-not (Test-Path $script)) {
    Write-Warning "discord_bridge.py missing"
    exit 0
}

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "discord_bridge\.py"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Process python -ArgumentList $script -WorkingDirectory $Root -WindowStyle Minimized
Write-Host "DISCORD_BRIDGE_STARTED"
