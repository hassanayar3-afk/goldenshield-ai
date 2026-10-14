# Cloudflare Named Tunnel autopilot (violafashioniq.com) — no secret output
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root

$py = & (Join-Path $Root "deploy\windows\Resolve-GsPython.ps1") -Root $Root
& $py -m pip install -r (Join-Path $Root "requirements.txt") -q 2>$null

$reportPath = Join-Path $Root "storage\runtime\tunnel_autopilot_report.json"
& $py (Join-Path $Root "deploy_ops\cloudflare_tunnel_autopilot.py") 2>&1 | Tee-Object -FilePath (Join-Path $Root "storage\logs\tunnel_autopilot.log")
$code = $LASTEXITCODE

try {
    & (Join-Path $Root "deploy\windows\Sync-GsMobileUrls.ps1") -Root $Root
} catch {}

if ($code -eq 0) {
    Write-Host "AUTOPILOT_OK permanent tunnel live"
} else {
    Write-Host "AUTOPILOT_INCOMPLETE see storage\runtime and logs\tunnel_autopilot.log"
}
exit $code
