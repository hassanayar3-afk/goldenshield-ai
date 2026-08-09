# -*- coding: utf-8 -*-
"""Remote status: bot, caddy, firewall, local health."""
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
ps = r"""
$ErrorActionPreference='SilentlyContinue'
Write-Output 'MANUAL_STOP='
Test-Path C:\saqr\storage\MANUAL_STOP.flag
Write-Output 'LISTEN'
netstat -ano | findstr LISTENING | findstr ':80 :443 :8090'
Write-Output 'LOCAL8090'
curl.exe -s -m 8 http://127.0.0.1:8090/health
Write-Output ''
Write-Output 'LOCAL_HTTPS'
curl.exe -sk -m 12 --resolve 169.58.15.36.sslip.io:443:127.0.0.1 https://169.58.15.36.sslip.io/health
Write-Output ''
Write-Output 'FW_SAQR'
Get-NetFirewallRule -DisplayName '*Saqr*' -ErrorAction SilentlyContinue | Select-Object DisplayName,Enabled,Direction,Action | Format-Table -AutoSize | Out-String
Write-Output 'CADDY'
Get-Process caddy -ErrorAction SilentlyContinue | Format-Table Id -AutoSize | Out-String
Write-Output 'UVICORN'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*' -and $_.CommandLine -like '*app.main*' } | ForEach-Object { $_.CommandLine.Substring(0,[Math]::Min(100,$_.CommandLine.Length)) }
Write-Output 'DONE'
"""
sftp = c.open_sftp()
with sftp.file("C:/saqr/_diag_now.ps1", "w") as f:
    f.write(ps)
sftp.close()
_i, o, e = c.exec_command(
    "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\saqr\\_diag_now.ps1",
    timeout=60,
)
text = (o.read() + e.read()).decode("utf-8", "replace")
Path(r"C:\Users\acer\goldenshield\GoldenShield_AI\_diag_now.txt").write_text(text, encoding="utf-8")
print(text.encode("ascii", "replace").decode("ascii"))
c.close()
