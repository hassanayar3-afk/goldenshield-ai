# Emergency quick tunnel for live preview (trycloudflare) — does not commit secrets.
param(
    [string]$Root = "C:\GoldenShield_Binance",
    [switch]$Force
)
$ErrorActionPreference = "Continue"
Set-Location $Root
. (Join-Path $Root "deploy\windows\Import-GsDotEnv.ps1") -EnvPath (Join-Path $Root ".env")

$allow = $Force -or ($env:GS_EMERGENCY_QUICK_TUNNEL -eq "true")
if (-not $allow) {
    Write-Warning "Set GS_EMERGENCY_QUICK_TUNNEL=true or use -Force"
    exit 2
}

$runtime = Join-Path $Root "storage\runtime"
$logs = Join-Path $Root "storage\logs"
New-Item -ItemType Directory -Force -Path $runtime, $logs | Out-Null
$logFile = Join-Path $logs "cloudflare_quick_preview.log"
$urlFile = Join-Path $runtime "mobile_tunnel_url.txt"

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    $bundled = Join-Path $Root "tools\cloudflared.exe"
    if (Test-Path $bundled) { $cf = Get-Command $bundled }
}
if (-not $cf) {
    Write-Error "cloudflared missing"
    exit 1
}

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "cloudflared"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Remove-Item $logFile -Force -ErrorAction SilentlyContinue
$port = 8790
if ($env:CLOUDFLARE_TUNNEL_LOCAL_URL -match ":(\d+)") { $port = [int]$Matches[1] }
Start-Process -FilePath $cf.Source -ArgumentList @(
    "tunnel", "--url", "http://127.0.0.1:$port",
    "--logfile", $logFile, "--loglevel", "info"
) -WorkingDirectory $Root -WindowStyle Hidden

$url = ""
$deadline = (Get-Date).AddMinutes(2)
while ((Get-Date) -lt $deadline -and -not $url) {
    Start-Sleep -Seconds 2
    if (-not (Test-Path $logFile)) { continue }
    $text = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
    if ($text -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
        $url = $Matches[1]
    }
}
if ($url) {
    ($url.TrimEnd("/") + "/") | Set-Content -Path $urlFile -Encoding UTF8
    Write-Output "QUICK_PREVIEW_OK $url"
    exit 0
}
Write-Warning "QUICK_PREVIEW_PENDING see $logFile"
exit 3
