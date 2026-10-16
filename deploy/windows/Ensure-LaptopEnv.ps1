# التحقق من .env للابتوب — إنشاء من القالب + تحذير بالقيم الناقصة
param(
    [string]$Root = "",
    [switch]$SkipContaboSyncCheck
)
$ErrorActionPreference = "Stop"
if (-not $Root) { $Root = (Get-Location).Path }
$envFile = Join-Path $Root ".env"
$tpl = Join-Path $Root "config\laptop.env.template"
if (-not (Test-Path $envFile)) {
    if (-not (Test-Path $tpl)) { throw ".env and config/laptop.env.template missing" }
    Copy-Item $tpl $envFile
    Write-Host "CREATED .env from config/laptop.env.template"
}

function Get-EnvMap([string]$Path) {
    $map = @{}
    Get-Content $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
        $k, $v = $line.Split("=", 2)
        $map[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
    }
    return $map
}

function Set-EnvLine([string]$Path, [string]$Key, [string]$Value) {
    $lines = Get-Content $Path -Encoding UTF8
    $found = $false
    $out = @()
    foreach ($l in $lines) {
        if ($l -match ('^\s*' + [regex]::Escape($Key) + '\s*=')) {
            $out += "$Key=$Value"
            $found = $true
        } else { $out += $l }
    }
    if (-not $found) { $out += "$Key=$Value" }
    Set-Content -Path $Path -Value $out -Encoding UTF8
}

$map = Get-EnvMap $envFile
$defaults = @{
    "GOLDENSHIELD_OFFICIAL_ROOT"      = $Root
    "BINANCE_DEMO_TRADING"            = "true"
    "EXECUTION_MODE"                  = "paper"
    "EXECUTION_BACKEND"               = "binance"
    "BINANCE_SKIP_LOAD_MARKETS"       = "true"
    "PROXY_URL"                       = ""
    "RUNTIME_SYNC_REMOTE_ROOT"        = "C:\GoldenShield_Binance"
    "RUNTIME_SYNC_INTERVAL_SEC"       = "15"
    "BOT_FORCE_ACTIVE"                = "true"
}
foreach ($k in $defaults.Keys) {
    if (-not $map[$k] -or $map[$k] -eq "") {
        Set-EnvLine $envFile $k $defaults[$k]
    }
}

$map = Get-EnvMap $envFile
$skipSync = $SkipContaboSyncCheck -or ($map["GS_SKIP_RUNTIME_SYNC"] -eq "true")
$required = @("BINANCE_API_KEY", "BINANCE_API_SECRET")
if (-not $skipSync) {
    $required += @("WIN_HOST", "WIN_USER")
}
$missing = @()
foreach ($k in $required) {
    $v = $map[$k]
    if (-not $v -or $v -eq "") { $missing += $k }
}
if (-not $skipSync) {
    $hasAuth = ($map["WIN_PASSWORD"] -and $map["WIN_PASSWORD"] -ne "") -or ($map["WIN_SSH_PRIVATE_KEY"] -and $map["WIN_SSH_PRIVATE_KEY"] -ne "")
    if (-not $hasAuth) { $missing += "WIN_PASSWORD or WIN_SSH_PRIVATE_KEY" }
}

$badProxy = @("your_proxy", "USERNAME:PASSWORD", "USER:PASS@IP", "your_proxy_ip")
if ($map["PROXY_URL"]) {
    foreach ($b in $badProxy) {
        if ($map["PROXY_URL"] -like "*$b*") {
            Set-EnvLine $envFile "PROXY_URL" ""
            Write-Host "CLEARED placeholder PROXY_URL (laptop should not use proxy template)"
            break
        }
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "=== .env incomplete — edit this file ===" -ForegroundColor Yellow
    Write-Host $envFile
    Write-Host "Missing or empty:" ($missing -join ", ")
    Write-Host "Fill values, save, then re-run GOLDENSHIELD_LAPTOP_ONE_SHOT.ps1"
    exit 2
}
Write-Host "ENV_OK $envFile"
exit 0
