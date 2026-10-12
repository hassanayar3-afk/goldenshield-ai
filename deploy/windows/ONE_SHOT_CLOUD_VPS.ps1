# نفّذ مرة واحدة على VPS (RDP → PowerShell مسؤول) — يربط Binance + Discord + Bot + API + جدار 8790
$ErrorActionPreference = "Stop"
$Root = "C:\GoldenShield_Binance"
Set-Location $Root

# جدار ناري — Mobile API
New-NetFirewallRule -DisplayName "GoldenShield Mobile API 8790" -Direction Inbound -Protocol TCP -LocalPort 8790 -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "GoldenShield WS 8791" -Direction Inbound -Protocol TCP -LocalPort 8791 -Action Allow -ErrorAction SilentlyContinue | Out-Null

if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\config\env.production.template" "$Root\.env" -Force
}
# عدّل .env يدوياً مرة واحدة: BINANCE_API_KEY, BINANCE_API_SECRET, DISCORD_WEBHOOK_URL

Set-ExecutionPolicy -Scope Process Bypass
& "$Root\deploy\windows\INSTALL_GOLDENSHIELD_TERMINAL.ps1"
& "$Root\deploy\windows\GS_START_FULL_STACK.ps1" -Root $Root

$health = Invoke-RestMethod -Uri "http://127.0.0.1:8790/api/health" -TimeoutSec 20
Write-Host "HEALTH" ($health | ConvertTo-Json -Compress)
Write-Host "APK_URL http://YOUR_PUBLIC_IP:8790/  or Cloudflare tunnel"
