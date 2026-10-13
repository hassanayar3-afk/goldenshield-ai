# Cloudflare Tunnel → يكتب https URL في storage/runtime/mobile_tunnel_url.txt
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $PSScriptRoot "Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")
if (-not ($env:MOBILE_PUBLIC_BASE_URL -match "^https?://")) {
    $env:CLOUDFLARE_TUNNEL_ENABLED = "true"
}

$enabled = ($env:CLOUDFLARE_TUNNEL_ENABLED -ne "false") -and ($env:CLOUDFLARE_TUNNEL_ENABLED -ne "0")
if (-not $enabled) {
    Write-Host "CLOUDFLARE_TUNNEL_DISABLED"
    exit 0
}

$runtime = Join-Path $Root "storage\runtime"
$logs = Join-Path $Root "storage\logs"
New-Item -ItemType Directory -Force -Path $runtime, $logs | Out-Null
$urlFile = Join-Path $runtime "mobile_tunnel_url.txt"
$logFile = Join-Path $logs "cloudflare_tunnel.log"
$logErr = Join-Path $logs "cloudflare_tunnel.err.log"
Remove-Item $logFile, $logErr -Force -ErrorAction SilentlyContinue

if ($env:MOBILE_PUBLIC_BASE_URL -match "^https?://") {
    ($env:MOBILE_PUBLIC_BASE_URL.TrimEnd("/") + "/") | Set-Content -Path $urlFile -Encoding UTF8 -NoNewline
    Add-Content -Path $urlFile -Value ""
    Write-Host "TUNNEL_STATIC_OK $($env:MOBILE_PUBLIC_BASE_URL)"
    exit 0
}

$token = $(if ($env:CLOUDFLARE_TUNNEL_TOKEN) { $env:CLOUDFLARE_TUNNEL_TOKEN } else { "" }).Trim()
$local = $(if ($env:CLOUDFLARE_TUNNEL_LOCAL_URL) { $env:CLOUDFLARE_TUNNEL_LOCAL_URL } else { "http://127.0.0.1:8790" }).Trim()
$port = 8790
if ($local -match ":(\d+)") { $port = [int]$Matches[1] }

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    $bundled = Join-Path $Root "tools\cloudflared.exe"
    if (Test-Path $bundled) { $cf = Get-Command $bundled }
}
if (-not $cf) {
    Write-Warning "cloudflared not found - set MOBILE_PUBLIC_BASE_URL in .env or install cloudflared"
    exit 0
}

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "cloudflared"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

if ($token) {
    Start-Process -FilePath $cf.Source -ArgumentList @(
        "tunnel", "run", "--token", $token,
        "--logfile", $logFile, "--loglevel", "info"
    ) -WorkingDirectory $Root -WindowStyle Hidden
    if ($env:MOBILE_PUBLIC_BASE_URL -match "^https?://") {
        ($env:MOBILE_PUBLIC_BASE_URL.TrimEnd("/") + "/") | Set-Content -Path $urlFile -Encoding UTF8 -NoNewline
        Add-Content -Path $urlFile -Value ""
        Write-Host "CLOUDFLARE_NAMED_TUNNEL_STARTED static=$($env:MOBILE_PUBLIC_BASE_URL)"
    } else {
        Write-Host "CLOUDFLARE_NAMED_TUNNEL_STARTED set MOBILE_PUBLIC_BASE_URL to your tunnel hostname - see $logFile"
    }
    exit 0
}

$target = "http://127.0.0.1:$port"
Start-Process -FilePath $cf.Source -ArgumentList @(
    "tunnel", "--url", $target,
    "--logfile", $logFile, "--loglevel", "info"
) -WorkingDirectory $Root -WindowStyle Hidden

$deadline = (Get-Date).AddMinutes(2)
$url = ""
while ((Get-Date) -lt $deadline -and -not $url) {
    Start-Sleep -Seconds 2
    if (-not (Test-Path $logFile)) { continue }
    $text = @(
        (Get-Content $logFile -Raw -ErrorAction SilentlyContinue),
        (Get-Content $logErr -Raw -ErrorAction SilentlyContinue)
    ) -join "`n"
    if ($text -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
        $url = $Matches[1]
    }
}
if ($url) {
    ($url.TrimEnd("/") + "/") | Set-Content -Path $urlFile -Encoding UTF8
    Write-Host "TUNNEL_QUICK_OK $url"
} else {
    Write-Warning "TUNNEL_URL_PENDING check $logFile"
}
