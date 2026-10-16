param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
if (-not $env:DISCORD_BOT_TOKEN) {
    Write-Warning "DISCORD_BOT_TOKEN missing"
    exit 2
}
$py = & (Join-Path $PSScriptRoot "Resolve-GsPython.ps1") -Root $Root
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "gs_discord_bot\.py"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath $py -ArgumentList @("$Root\gs_discord_bot.py") -WorkingDirectory $Root -WindowStyle Hidden
Write-Host "GS_DISCORD_BOT_STARTED"
