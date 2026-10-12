# تحميل GoldenShield-Control.apk إلى سطح المكتب (مستودع خاص — GitHub Releases)
$ErrorActionPreference = "Stop"
$Desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "GoldenShield-Control.apk"
$tag = "control-apk-p1"
gh release download $tag -R hassanayar3-afk/goldenshield-ai -p "GoldenShield-Control.apk" -D ([Environment]::GetFolderPath("Desktop")) --clobber
Write-Host "APK_OK $Desktop"
