# -*- coding: utf-8 -*-
"""Fix HTTPS: start Caddy, clean FW dupes lightly, clear accidental manual stop, verify."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(r"C:\Users\acer\goldenshield\GoldenShield_AI\.env"), override=True)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    os.getenv("WIN_HOST").strip(),
    username=os.getenv("WIN_USER").strip(),
    password=os.getenv("WIN_PASSWORD").strip(),
    timeout=30,
    allow_agent=False,
    look_for_keys=False,
)

ensure_caddy = r'''$ErrorActionPreference="SilentlyContinue"
$exe="C:\saqr\caddy\caddy.exe"
$dir="C:\saqr\caddy"
if (-not (Test-Path $exe)) { Write-Output "NO_CADDY"; exit 0 }
# firewall once (no spam duplicates)
$need80 = -not (Get-NetFirewallRule -DisplayName "Saqr HTTP 80" -ErrorAction SilentlyContinue | Select-Object -First 1)
$need443 = -not (Get-NetFirewallRule -DisplayName "Saqr HTTPS 443" -ErrorAction SilentlyContinue | Select-Object -First 1)
if ($need80) { New-NetFirewallRule -DisplayName "Saqr HTTP 80" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow -Profile Any | Out-Null }
if ($need443) { New-NetFirewallRule -DisplayName "Saqr HTTPS 443" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow -Profile Any | Out-Null }
Get-NetFirewallRule -DisplayName "Saqr HTTP 80","Saqr HTTPS 443" -ErrorAction SilentlyContinue | Set-NetFirewallRule -Enabled True -Action Allow -Profile Any
$listening443 = netstat -ano | findstr LISTENING | findstr ":443 "
if ($listening443 -and (Get-Process caddy -ErrorAction SilentlyContinue)) {
  Write-Output "CADDY_ALREADY"
  exit 0
}
Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
& $exe stop 2>$null
Start-Sleep 1
Push-Location $dir
& $exe start --config (Join-Path $dir "Caddyfile")
Pop-Location
Start-Sleep 3
if (Get-Process caddy -ErrorAction SilentlyContinue) { "CADDY_OK" } else { "CADDY_FAIL" }
'''

ps = r"""
$ErrorActionPreference='SilentlyContinue'
# For shop recovery now: clear manual stop so bot stays managed normally
Remove-Item 'C:\saqr\storage\MANUAL_STOP.flag' -Force -ErrorAction SilentlyContinue
powershell -NoProfile -ExecutionPolicy Bypass -File C:\saqr\ENSURE_BOT.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File C:\saqr\ENSURE_CADDY.ps1
Start-Sleep 4
Write-Output 'LISTEN'
netstat -ano | findstr LISTENING | findstr ':80 :443 :8090'
Write-Output 'LOCAL8090'
curl.exe -s -m 8 http://127.0.0.1:8090/health
Write-Output ''
Write-Output 'LOCAL443'
curl.exe -sk -m 15 --resolve 169.58.15.36.sslip.io:443:127.0.0.1 https://169.58.15.36.sslip.io/health
Write-Output ''
Write-Output 'CADDY_PROC'
Get-Process caddy -ErrorAction SilentlyContinue | Format-Table Id,ProcessName -AutoSize | Out-String
Write-Output 'MANUAL_STOP'
Test-Path C:\saqr\storage\MANUAL_STOP.flag
Write-Output 'DONE'
"""

sftp = c.open_sftp()
with sftp.file("C:/saqr/ENSURE_CADDY.ps1", "w") as f:
    f.write(ensure_caddy)
with sftp.file("C:/saqr/_fix_https_now.ps1", "w") as f:
    f.write(ps)
sftp.close()

_i, o, e = c.exec_command(
    "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\saqr\\_fix_https_now.ps1",
    timeout=90,
)
text = (o.read() + e.read()).decode("utf-8", "replace")
Path(r"C:\Users\acer\goldenshield\GoldenShield_AI\_fix_https_now.txt").write_text(
    text, encoding="utf-8"
)
print(text.encode("ascii", "replace").decode("ascii")[:2500])
c.close()
