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
    "BINANCE_DEMO_TRADING", "BINANCE_HTTPS_PROXY", "BINANCE_DEMO_API_PUBLIC", "BINANCE_DEMO_API_PRIVATE",
    "EXECUTION_MODE", "EXECUTION_BACKEND",
    "DISCORD_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID", "DISCORD_NOTIFY_ENABLED",
    "DISCORD_BOT_USERNAME", "DISCORD_BRIDGE_INTERVAL_SEC",
    "CLOUDFLARE_TUNNEL_TOKEN", "CLOUDFLARE_TUNNEL_ENABLED", "CLOUDFLARE_TUNNEL_LOCAL_URL",
    "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_GLOBAL_API_KEY", "CLOUDFLARE_EMAIL", "CLOUDFLARE_API_EMAIL",
    "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_ZONE_ID", "CLOUDFLARE_TUNNEL_NAME",
    "MOBILE_PUBLIC_BASE_URL", "MOBILE_PAIR_CODE", "MOBILE_API_TOKEN", "MOBILE_PUBLIC_IP", "GS_PANEL_PUBLIC_HOST",
    "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_MUTE_ALL", "TELEGRAM_OUTBOUND_DISABLED",
    "WIN_HOST", "WIN_USER", "WIN_PASSWORD",
    "GS_BAN_QUICK_TUNNEL"
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

function Is-Blank([string]$Value) {
    return [string]::IsNullOrWhiteSpace($Value)
}

function Merge-Into([hashtable]$Target, [hashtable]$Source, [string[]]$AllowKeys, [switch]$OnlyIfBlank) {
    foreach ($entry in $Source.GetEnumerator()) {
        if ($AllowKeys -notcontains $entry.Key) { continue }
        if (Is-Blank $entry.Value) { continue }
        if ($OnlyIfBlank -and -not (Is-Blank $Target[$entry.Key])) { continue }
        $Target[$entry.Key] = $entry.Value
    }
}

$merged = Parse-EnvFile $masterEnv
$sources = @(
    (Join-Path $Root "goldenshield.env"),
    (Join-Path $Root "storage\runtime\mobile_api_credentials.txt")
)

Get-ChildItem $backupDir -Filter ".env.*.bak" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime |
    ForEach-Object { $sources += $_.FullName }

foreach ($glob in @("C:\GoldenShield*\*.env")) {
    Get-ChildItem $glob -ErrorAction SilentlyContinue | ForEach-Object { $sources += $_.FullName }
}

foreach ($src in ($sources | Select-Object -Unique)) {
    Merge-Into $merged (Parse-EnvFile $src) $keys -OnlyIfBlank
}

$discordJson = Join-Path $Root "storage\runtime\discord_bridge.json"
if (Test-Path $discordJson) {
    try {
        $dj = Get-Content $discordJson -Raw -Encoding UTF8 | ConvertFrom-Json
        $map = @{}
        if ($dj.webhook_url) { $map["DISCORD_WEBHOOK_URL"] = [string]$dj.webhook_url }
        if ($dj.bot_token) { $map["DISCORD_BOT_TOKEN"] = [string]$dj.bot_token }
        if ($dj.channel_id) { $map["DISCORD_CHANNEL_ID"] = [string]$dj.channel_id }
        if ($dj.username) { $map["DISCORD_BOT_USERNAME"] = [string]$dj.username }
        Merge-Into $merged $map $keys -OnlyIfBlank
    } catch { }
}

$tunnelUrlFile = Join-Path $Root "storage\runtime\mobile_tunnel_url.txt"
if (Test-Path $tunnelUrlFile) {
    try {
        $tu = (Get-Content $tunnelUrlFile -Raw -Encoding UTF8).Trim().Trim('"')
        if ($tu -match "^https?://") {
            if (-not $tu.EndsWith("/")) { $tu = $tu + "/" }
            if (Is-Blank $merged["MOBILE_PUBLIC_BASE_URL"]) {
                $merged["MOBILE_PUBLIC_BASE_URL"] = $tu
            }
        }
    } catch { }
}

if (Is-Blank $merged["MOBILE_PUBLIC_BASE_URL"]) {
    $merged["MOBILE_PUBLIC_BASE_URL"] = "https://violafashioniq.com/"
}
if (Is-Blank $merged["CLOUDFLARE_TUNNEL_LOCAL_URL"]) {
    $merged["CLOUDFLARE_TUNNEL_LOCAL_URL"] = "http://127.0.0.1:8790"
}
if (Is-Blank $merged["GS_BAN_QUICK_TUNNEL"]) {
    $merged["GS_BAN_QUICK_TUNNEL"] = "true"
}
if (Is-Blank $merged["CLOUDFLARE_TUNNEL_ENABLED"]) {
    $merged["CLOUDFLARE_TUNNEL_ENABLED"] = "true"
}

$raw = ""
if (Test-Path $masterEnv) { $raw = Get-Content $masterEnv -Raw -Encoding UTF8 }
foreach ($k in $keys) {
    $val = $merged[$k]
    if (Is-Blank $val) { continue }
    $line = "$k=$val"
    if ($raw -match "(?m)^$([regex]::Escape($k))=.*$") {
        $raw = [regex]::Replace($raw, "(?m)^$([regex]::Escape($k))=.*$", $line, 1)
    } else {
        $raw = $raw.TrimEnd() + "`n$line`n"
    }
}
Set-Content -Path $masterEnv -Value $raw -Encoding UTF8
Write-Host "HARVEST_OK backup=$backupDir"
