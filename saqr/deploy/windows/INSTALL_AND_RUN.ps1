# SAQR — تثبيت Rust/Git (إن لزم) وتشغيل البوت على Windows VPS
$ErrorActionPreference = "Stop"
$SaqrRoot = "C:\Saqr"
$RepoDir = Join-Path $SaqrRoot "Saqr"

New-Item -ItemType Directory -Force -Path $SaqrRoot | Out-Null

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "Installing Git..."
  winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
  Write-Host "Installing Rust..."
  $rustup = Join-Path $env:TEMP "rustup-init.exe"
  Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile $rustup
  & $rustup -y --default-toolchain stable
  $env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
}

if (-not (Test-Path $RepoDir)) {
  git clone https://github.com/hassanayar93/Saqr.git $RepoDir
} else {
  Set-Location $RepoDir
  git pull origin main
}

Set-Location $RepoDir
if (-not (Test-Path ".env")) {
  Write-Host "Copy .env to $RepoDir before running."
  exit 1
}

cargo build --release
Start-Process -FilePath ".\target\release\saqr.exe" -WorkingDirectory $RepoDir
Write-Host "SAQR started. Dashboard: http://$((Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*'})[0].IPAddress):8787"
