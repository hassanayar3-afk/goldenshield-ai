"""Deploy UI Arabic reports + live stats + icon sizing."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import paramiko

FILES = [
    r"web\assets\js\config.js",
    r"web\assets\js\ui.js",
    r"web\assets\js\pages\analytics.js",
    r"web\assets\js\pages\operations.js",
    r"web\assets\js\pages\settings.js",
    r"web\assets\js\pages\home.js",
    r"web\pages\analytics.html",
    r"web\pages\operations.html",
    r"web\pages\settings.html",
    r"web\index.html",
    r"web\assets\css\layout.css",
    r"web\assets\css\components.css",
    r"app\main.py",
]

load_dotenv(Path(r"C:\Users\acer\goldenshield\GoldenShield_AI\.env"), override=True)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    os.getenv("WIN_HOST").strip(),
    username=os.getenv("WIN_USER").strip(),
    password=os.getenv("WIN_PASSWORD").strip(),
    timeout=40,
    allow_agent=False,
    look_for_keys=False,
)
sftp = c.open_sftp()
base = Path(r"C:\Users\acer\hassan")
for rel in FILES:
    local = base / rel
    remote = r"C:\saqr\\" + rel.replace("/", "\\")
    # ensure remote dir
    remote_dir = str(Path(remote).parent)
    try:
        sftp.stat(remote_dir)
    except OSError:
        pass
    sftp.put(str(local), remote)
    print("put", rel)
sftp.close()


def run(cmd: str, timeout: int = 120) -> str:
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.recv_exit_status()
    return (o.read() + e.read()).decode("utf-8", "replace")


ps = r'''
$ErrorActionPreference='Continue'
$conns = Get-NetTCPConnection -LocalPort 8090 -EA SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $conns) { if ($procId) { Stop-Process -Id $procId -Force -EA SilentlyContinue } }
Start-Sleep 2
Remove-Item C:\saqr\storage\MANUAL_STOP.flag -Force -EA SilentlyContinue
$env:PORT='8090'
Start-Process -FilePath 'C:\saqr\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8090' -WorkingDirectory 'C:\saqr' -WindowStyle Hidden
Start-Sleep 6
try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 12 http://127.0.0.1:8090/health).Content } catch { $_.Exception.Message }
'''
sftp = c.open_sftp()
with sftp.file(r"C:\saqr\_restart286.ps1", "w") as f:
    f.write(ps)
sftp.close()
print(run(r"powershell -NoProfile -ExecutionPolicy Bypass -File C:\saqr\_restart286.ps1", timeout=90))
c.close()
print("DONE")
