# Restart PM2 stack from sovereign root (Windows)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
$env:GOLDENSHIELD_OFFICIAL_ROOT = $Root
. (Join-Path $Root "deploy\windows\Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")

if (-not (Get-Command pm2 -ErrorAction SilentlyContinue)) {
    Write-Warning "pm2 not in PATH — install: npm i -g pm2"
    exit 2
}

$py = & (Join-Path $Root "deploy\windows\Resolve-GsPython.ps1") -Root $Root
$env:GS_PYTHON = $py
$env:GATEWAY_API_PORT = $(if ($env:GATEWAY_API_PORT) { $env:GATEWAY_API_PORT } else { "8792" })

pm2 delete GS-Gateway, GS-NeuralCore, GS-Tunnel, GS-MobileApi -s 2>$null | Out-Null
pm2 start (Join-Path $Root "deploy_ops\pm2.ecosystem.config.cjs") --update-env
Start-Sleep -Seconds 8
pm2 logs GS-Gateway --lines 50 --nostream 2>&1 | Out-String | Write-Host
pm2 logs GS-NeuralCore --lines 50 --nostream 2>&1 | Out-String | Write-Host
pm2 status
Write-Host "PM2_STACK_OK"
