# Phase 1 — backup + merge secrets into C:\GoldenShield_Binance\.env (no secret output)
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Stop"
Set-Location $Root

$backupDir = Join-Path $Root "storage\runtime\secrets_harvest"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$masterEnv = Join-Path $Root ".env"

function Backup-File([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $name = Split-Path $Path -Leaf
    Copy-Item $Path (Join-Path $backupDir ($name + "." + $stamp + ".bak")) -Force
}

Backup-File $masterEnv
Backup-File (Join-Path $Root "goldenshield.env")
Backup-File (Join-Path $Root "storage\runtime\mobile_api_credentials.txt")

$keys = @(
    "BINANCE_API_KEY", "BINANCE_API_SECRET", "BINANCE_API_KEY_2", "BINANCE_API_SECRET_2",
    "DISCORD_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID",
    "CLOUDFLARE_TUNNEL_TOKEN", "MOBILE_PUBLIC_BASE_URL", "MOBILE_PAIR_CODE", "MOBILE_API_TOKEN",
    "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "GS_BAN_QUICK_TUNNEL", "CLOUDFLARE_TUNNEL_ENABLED"
)

function Parse-EnvFile([string]$Path) {
    $map = @{}
    if (-not (Test-Path $Path)) { return $map }
    foreach ($line in Get-Content $Path -Encoding UTF8) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#") -or $t -notmatch "=") { continue }
        $k, $v = $t.Split("=", 2)
        $map[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
    }
    return $map
}

$merged = Parse-EnvFile $masterEnv
$sources = @(
    $masterEnv,
    (Join-Path $Root "goldenshield.env"),
    (Join-Path $Root "storage\runtime\mobile_api_credentials.txt")
)
foreach ($glob in @("C:\GoldenShield*\*.env")) {
    Get-ChildItem $glob -ErrorAction SilentlyContinue | ForEach-Object { $sources += $_.FullName }
}

foreach ($src in ($sources | Select-Object -Unique)) {
    foreach ($entry in (Parse-EnvFile $src).GetEnumerator()) {
        if ($entry.Key -in $keys -and $entry.Value) {
            if (-not $merged[$entry.Key]) { $merged[$entry.Key] = $entry.Value }
        }
    }
}

if (-not $merged["MOBILE_PUBLIC_BASE_URL"]) {
    $merged["MOBILE_PUBLIC_BASE_URL"] = "https://violafashioniq.com/"
}
$merged["GS_BAN_QUICK_TUNNEL"] = "true"
$merged["CLOUDFLARE_TUNNEL_ENABLED"] = "true"

$raw = ""
if (Test-Path $masterEnv) { $raw = Get-Content $masterEnv -Raw -Encoding UTF8 }
foreach ($k in $keys) {
    $val = $merged[$k]
    if (-not $val) { continue }
    $line = "$k=$val"
    if ($raw -match "(?m)^$([regex]::Escape($k))=.*$") {
        $raw = [regex]::Replace($raw, "(?m)^$([regex]::Escape($k))=.*$", $line, 1)
    } else {
        $raw = $raw.TrimEnd() + "`n$line`n"
    }
}
Set-Content -Path $masterEnv -Value $raw -Encoding UTF8
Write-Host "HARVEST_OK backup=$backupDir"
