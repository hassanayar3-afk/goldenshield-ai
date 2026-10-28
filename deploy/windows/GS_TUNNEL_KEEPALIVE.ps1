# Keeps cloudflared quick tunnel running (separate from short GS_START parent)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $Root "deploy\windows\Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
if (-not ($env:MOBILE_PUBLIC_BASE_URL -match "^https?://")) {
    $env:CLOUDFLARE_TUNNEL_ENABLED = "true"
}
if ($env:CLOUDFLARE_TUNNEL_ENABLED -eq "false" -or $env:CLOUDFLARE_TUNNEL_ENABLED -eq "0") {
    exit 0
}
$startScript = Join-Path $Root "deploy\windows\START_CLOUDFLARE_TUNNEL.ps1"
$staticUrl = ($env:MOBILE_PUBLIC_BASE_URL -match "^https?://")
$namedToken = [bool]($env:CLOUDFLARE_TUNNEL_TOKEN -and $env:CLOUDFLARE_TUNNEL_TOKEN.Trim())
while ($true) {
    try {
        if ($staticUrl -and (Test-Path $startScript)) {
            & $startScript -Root $Root
            Start-Sleep -Seconds 300
            continue
        }
        $cf = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -and $_.CommandLine -match "cloudflared"
        }).Count
        if ($cf -lt 1 -and (Test-Path $startScript)) {
            & $startScript -Root $Root
        }
    } catch {}
    $sleepSec = if ($namedToken) { 60 } else { 45 }
    Start-Sleep -Seconds $sleepSec
}
