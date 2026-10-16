# بناء APK على اللابتوب (Windows) ونسخه إلى سطح المكتب + downloads
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $Here "..\..")
$AndroidDir = Join-Path $Root "mobile_android"
$ApkOut = Join-Path $AndroidDir "app\build\outputs\apk\debug\app-debug.apk"
$DestRepo = Join-Path $Root "downloads\GoldenShield-Control.apk"
$DestPublic = "C:\Users\Public\GoldenShield-Control.apk"
$Desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "GoldenShield-Control.apk"

if (-not $env:ANDROID_HOME) {
    $guess = Join-Path $env:LOCALAPPDATA "Android\Sdk"
    if (Test-Path $guess) { $env:ANDROID_HOME = $guess }
}
if (-not $env:ANDROID_HOME) {
    throw "Set ANDROID_HOME to Android SDK (Android Studio default: %LOCALAPPDATA%\Android\Sdk)"
}

Set-Location $AndroidDir
if (-not (Test-Path ".\gradlew.bat")) {
    throw "gradlew.bat missing — sync repo or run: gradle wrapper"
}
& .\gradlew.bat assembleDebug
if (-not (Test-Path $ApkOut)) { throw "Build failed: $ApkOut" }

New-Item -ItemType Directory -Force -Path (Join-Path $Root "downloads") | Out-Null
Copy-Item $ApkOut $DestRepo -Force
Copy-Item $ApkOut $DestPublic -Force
Copy-Item $ApkOut $Desktop -Force
Write-Host "APK_DESKTOP_OK $Desktop"
Write-Host "APK_REPO_OK $DestRepo"
