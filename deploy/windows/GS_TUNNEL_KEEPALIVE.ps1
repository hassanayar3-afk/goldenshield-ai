# Keeps cloudflared quick tunnel running (separate from short GS_START parent)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $Root "deploy\windows\Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
if ($env:CLOUDFLARE_TUNNEL_ENABLED -eq "false" -or $env:CLOUDFLARE_TUNNEL_ENABLED -eq "0") {
    exit 0
}
$startScript = Join-Path $Root "deploy\windows\START_CLOUDFLARE_TUNNEL.ps1"
while ($true) {
    try {
        $cf = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -and $_.CommandLine -match "cloudflared"
        }).Count
        if ($cf -lt 1 -and (Test-Path $startScript)) {
            & $startScript -Root $Root
        }
    } catch {}
    Start-Sleep -Seconds 45
}
