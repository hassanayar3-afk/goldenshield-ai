# Persist MOBILE_PAIR_CODE + MOBILE_PUBLIC_BASE_URL in .env (stable pairing / public URL).
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
$envPath = Join-Path $Root ".env"
$credPath = Join-Path $Root "storage\runtime\mobile_api_credentials.txt"
if (-not (Test-Path $envPath)) { return }

function Set-EnvLine {
    param([string]$Key, [string]$Value)
    if (-not $Value) { return }
    $raw = Get-Content $envPath -Raw -Encoding UTF8
    $line = "$Key=$Value"
    if ($raw -match "(?m)^$([regex]::Escape($Key))=.*$") {
        $raw = [regex]::Replace($raw, "(?m)^$([regex]::Escape($Key))=.*$", $line, 1)
    } else {
        $raw = $raw.TrimEnd() + "`n$line`n"
    }
    Set-Content -Path $envPath -Value $raw -Encoding UTF8
}

. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath $envPath

if (Test-Path $credPath) {
    $pair = ""
    foreach ($ln in Get-Content $credPath -Encoding UTF8) {
        if ($ln -match "^MOBILE_PAIR_CODE=(.+)$") { $pair = $Matches[1].Trim().ToUpper() }
    }
    if ($pair -and $pair -notmatch "^(GS-GOLD80|GOLD80)$") {
        Set-EnvLine -Key "MOBILE_PAIR_CODE" -Value $pair
        $env:MOBILE_PAIR_CODE = $pair
        Write-Host "MOBILE_PAIR_CODE_PERSISTED hint=$($pair.Substring(0,3))***"
    }
}

if ($env:MOBILE_PUBLIC_BASE_URL -match "^https?://") {
    $base = $env:MOBILE_PUBLIC_BASE_URL.Trim().TrimEnd("/") + "/"
    $urlFile = Join-Path $Root "storage\runtime\mobile_tunnel_url.txt"
    New-Item -ItemType Directory -Force -Path (Split-Path $urlFile -Parent) | Out-Null
    Set-Content -Path $urlFile -Value $base -Encoding UTF8 -NoNewline
    Add-Content -Path $urlFile -Value ""
    Write-Host "MOBILE_PUBLIC_BASE_URL_ACTIVE"
}
