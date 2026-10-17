# Remove stale quick-tunnel artifacts, duplicate cloudflared, old APK copies, temp deploy files.
param(
    [string]$Root = "C:\GoldenShield_Binance",
    [switch]$Aggressive
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")

$runtime = Join-Path $Root "storage\runtime"
$logs = Join-Path $Root "storage\logs"
$temp = $env:TEMP

Write-Host "=== Cleanup-GsLegacy Root=$Root ==="

# Temp zip/b64 from cloud deploy
Get-ChildItem $temp -Filter "gs_*.zip" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $temp -Filter "gs_*" -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Root -Filter "*.b64part" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

$useStatic = $env:MOBILE_PUBLIC_BASE_URL -match "^https?://"
$useNamed = [bool]($env:CLOUDFLARE_TUNNEL_TOKEN -and $env:CLOUDFLARE_TUNNEL_TOKEN.Trim())

# Stop duplicate cloudflared (leave at most one when quick/named tunnel active)
$cfProcs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "cloudflared"
})
if ($useStatic) {
    foreach ($p in $cfProcs) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "CLOUDFLARED_STOPPED (static MOBILE_PUBLIC_BASE_URL)"
} elseif ($cfProcs.Count -gt 1) {
    $keep = $cfProcs[-1].ProcessId
    foreach ($p in $cfProcs) {
        if ($p.ProcessId -ne $keep) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host ("CLOUDFLARED_DEDUPED kept=" + $keep)
}

# Purge dead trycloudflare hostnames from config/assets when we have a canonical URL
$urlFile = Join-Path $runtime "mobile_tunnel_url.txt"
$canonical = ""
if ($useStatic) {
    $canonical = $env:MOBILE_PUBLIC_BASE_URL.Trim().TrimEnd("/")
} elseif (Test-Path $urlFile) {
    $canonical = (Get-Content $urlFile -Raw -ErrorAction SilentlyContinue).Trim().TrimEnd("/")
}

if ($canonical -match "^https://") {
    ($canonical + "/") | Set-Content -Path $urlFile -Encoding UTF8 -NoNewline
    Add-Content -Path $urlFile -Value ""
    $paths = @(
        (Join-Path $Root "config\mobile_default_servers.txt"),
        (Join-Path $Root "mobile_android\app\src\main\assets\default_servers.txt")
    )
    foreach ($p in $paths) {
        if (-not (Test-Path (Split-Path $p -Parent))) { continue }
        Set-Content -Path $p -Value ($canonical + "/") -Encoding UTF8
    }
}

if ($Aggressive) {
    # Old oversized APK (pre v2.2) outside canonical locations
    $canonicalApk = Join-Path $Root "downloads\GoldenShield-Control.apk"
    $sizes = @{}
    if (Test-Path $canonicalApk) { $sizes[$canonicalApk] = (Get-Item $canonicalApk).Length }
    $pubApk = "C:\Users\Public\GoldenShield-Control.apk"
    if ((Test-Path $canonicalApk) -and (Test-Path $pubApk)) {
        $canonLen = (Get-Item $canonicalApk).Length
        if ((Get-Item $pubApk).Length -ne $canonLen) {
            Copy-Item $canonicalApk $pubApk -Force
        }
    }
    foreach ($glob in @(
        (Join-Path $Root "GoldenShield-Control.apk"),
        (Join-Path $Root "storage\mobile\*.apk")
    )) {
        Get-ChildItem $glob -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.FullName -eq $canonicalApk) { return }
            Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
            Write-Host ("OLD_APK_REMOVED " + $_.FullName)
        }
    }
    # Truncate huge tunnel logs (keep last quick-tunnel noise down)
    foreach ($lf in @(
        (Join-Path $logs "cloudflare_tunnel.log"),
        (Join-Path $logs "cloudflare_tunnel.err.log")
    )) {
        if ((Test-Path $lf) -and ((Get-Item $lf).Length -gt 2MB)) {
            Set-Content -Path $lf -Value "# truncated by Cleanup-GsLegacy" -Encoding UTF8
        }
    }
}

Write-Host "=== Cleanup-GsLegacy_DONE ==="
