# صقر SAQR — تشغيل البوت على Windows (Contabo)
$ErrorActionPreference = "Stop"
$SaqrRoot = "C:\Saqr"
Set-Location $SaqrRoot

if (-not (Test-Path "$SaqrRoot\.env")) {
    Write-Host "Missing C:\Saqr\.env — copy saqr.env first" -ForegroundColor Red
    exit 1
}

$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path

if (-not (Test-Path "$SaqrRoot\target\release\saqr.exe")) {
    Write-Host "Building SAQR (first run may take several minutes)..."
    cargo build --release
}

Write-Host "Starting SAQR Engine + Control Terminal on port 8787..."
Start-Process -FilePath "$SaqrRoot\target\release\saqr.exe" -WorkingDirectory $SaqrRoot -WindowStyle Normal
