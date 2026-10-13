# يحدّث روابط النفق/APK بعد كل نشر — يحذف الاعتماد على trycloudflare القديم في الملفات
param(
    [string]$Root = "C:\GoldenShield_Binance"
)
$ErrorActionPreference = "Continue"
Set-Location $Root

$tunFile = Join-Path $Root "storage\runtime\mobile_tunnel_url.txt"
$tun = ""
if (Test-Path $tunFile) {
    $tun = (Get-Content $tunFile -Raw -ErrorAction SilentlyContinue).Trim().TrimEnd("/")
}
if ($tun -notmatch "^https://") {
    Write-Warning "TUNNEL_URL_MISSING — run START_CLOUDFLARE_TUNNEL.ps1"
    exit 0
}

$configPath = Join-Path $Root "config\mobile_default_servers.txt"
$assetPath = Join-Path $Root "mobile_android\app\src\main\assets\default_servers.txt"
# سطر واحد فقط — لا روابط trycloudflare قديمة متعددة (سبب تشتت APK/اللوحة)
$configBody = @(
    "# auto-sync $(Get-Date -Format o)",
    "# active tunnel (single source)",
    $tun
) -join "`n"
Set-Content -Path $configPath -Value $configBody -Encoding UTF8
New-Item -ItemType Directory -Force -Path (Split-Path $assetPath -Parent) | Out-Null
Set-Content -Path $assetPath -Value ($tun + "/") -Encoding UTF8

$apkSrc = Join-Path $Root "downloads\GoldenShield-Control.apk"
$apkPub = "C:\Users\Public\GoldenShield-Control.apk"
if (Test-Path $apkSrc) {
    Copy-Item $apkSrc $apkPub -Force
}
Write-Output "MOBILE_URL_SYNC_OK $tun"
