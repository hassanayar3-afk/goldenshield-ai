# ينظّم ملفات GoldenShield على سطح المكتب: يحفظ المهم في C:\GoldenShield_Binance ويزيل النسخ القديمة غير المرتبطة
$ErrorActionPreference = "Stop"
$Project = "C:\GoldenShield_Binance"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ImportDir = Join-Path $Project "_desktop_import"
$DownloadsDir = Join-Path $Project "downloads"

if (-not (Test-Path $Project)) {
    throw "المشروع غير موجود: $Project — عدّل `$Project في السكربت إن كان المسار مختلفاً"
}
New-Item -ItemType Directory -Force -Path $ImportDir, $DownloadsDir | Out-Null

$keepOnDesktop = @(
    "GoldenShield START 24-7.lnk",
    "GoldenShield STOP.lnk",
    "GoldenShield Panel.lnk"
)

Get-ChildItem $Desktop -Force | ForEach-Object {
    $name = $_.Name
    if ($keepOnDesktop -contains $name) { return }

    $isGs = $name -match "(?i)goldenshield"
    $isOldLauncher = $name -match "^(START_BOT|STOP_BOT|REST_BOT|BOT_WINDOW|START_BOT_24_7|STOP_BOT_FULL)\.(bat|cmd|ps1)$"

    if (-not $isGs -and -not $isOldLauncher) { return }

    if ($name -eq "GoldenShield-Control.apk") {
        $dest = Join-Path $DownloadsDir "GoldenShield-Control.apk"
        Move-Item $_.FullName $dest -Force
        Write-Host "MOVED_APK -> $dest"
        return
    }

    $dest = Join-Path $ImportDir $name
    if (Test-Path $dest) { Remove-Item $_.FullName -Force; Write-Host "DELETED_DUPLICATE $name"; return }
    Move-Item $_.FullName $dest -Force
    Write-Host "MOVED -> $dest"
}

Write-Host "DONE Desktop=$Desktop Project=$Project"
