# تحميل GoldenShield-Control.apk إلى سطح المكتب (مستودع خاص — GitHub Releases)
$ErrorActionPreference = "Stop"
$Desktop = [Environment]::GetFolderPath("Desktop")
$OutFile = Join-Path $Desktop "GoldenShield-Control.apk"
$tag = "control-apk-v1.2"
$repo = "hassanayar3-afk/goldenshield-ai"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "GH_MISSING Install GitHub CLI then: gh auth login"
    Write-Host "BROWSER https://github.com/$repo/releases/tag/$tag"
    exit 1
}

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "GH_AUTH_REQUIRED Run: gh auth login"
    Write-Host "BROWSER https://github.com/$repo/releases/tag/$tag"
    exit 1
}

gh release download $tag -R $repo -p "GoldenShield-Control.apk" -D $Desktop --clobber
if (-not (Test-Path $OutFile)) {
    throw "Download failed — open release in browser"
}
Write-Host "APK_OK $OutFile"
