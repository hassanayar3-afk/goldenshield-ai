# تثبيت Git + Rust + استنساخ Saqr (مرة واحدة)
$ErrorActionPreference = "Continue"
$SaqrRoot = "C:\Saqr"
New-Item -ItemType Directory -Force -Path $SaqrRoot | Out-Null

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    winget install -e --id Rustlang.Rustup --accept-package-agreements --accept-source-agreements
}

$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path

if (-not (Test-Path "$SaqrRoot\.git")) {
    git clone https://github.com/hassanayar93/Saqr.git $SaqrRoot
} else {
    Set-Location $SaqrRoot
    git pull
}

Write-Host "Done. Place .env in C:\Saqr then run START_SAQR.bat"
