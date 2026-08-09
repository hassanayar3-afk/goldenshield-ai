"""Deploy training memory update to Saqr VPS."""
from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
import paramiko

FILES = [
    (r"C:\Users\acer\hassan\app\store.py", r"C:\saqr\app\store.py"),
    (r"C:\Users\acer\hassan\app\training_rules.py", r"C:\saqr\app\training_rules.py"),
    (r"C:\Users\acer\hassan\app\admin.py", r"C:\saqr\app\admin.py"),
    (r"C:\Users\acer\hassan\app\main.py", r"C:\saqr\app\main.py"),
    (r"C:\Users\acer\hassan\web\pages\training.html", r"C:\saqr\web\pages\training.html"),
    (r"C:\Users\acer\hassan\web\assets\js\pages\training.js", r"C:\saqr\web\assets\js\pages\training.js"),
    (r"C:\Users\acer\hassan\web\assets\js\api.js", r"C:\saqr\web\assets\js\api.js"),
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
for local, remote in FILES:
    sftp.put(local, remote)
    print("put", Path(local).name)
sftp.close()


def run(cmd: str, timeout: int = 120) -> str:
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    o.channel.recv_exit_status()
    return (o.read() + e.read()).decode("utf-8", "replace")


# migrate + smoke
print(
    run(
        r'C:\saqr\.venv\Scripts\python.exe -c '
        r'"from app.store import ConversationStore; '
        r's=ConversationStore(); '
        r'i=s.add_training_lesson(\"بكم التوصيل؟ => التوصيل حسب المحافظة\"); '
        r'print(\"lesson\", i); '
        r'print(\"cols_ok\", bool(s.list_training_lessons(limit=1))); '
        r'from app import main; print(\"ver\", main.APP_VERSION, \"ai\", main.USE_AI)"'
    )
)

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
with sftp.file(r"C:\saqr\_deploy_train.ps1", "w") as f:
    f.write(ps)
sftp.close()
print(run(r"powershell -NoProfile -ExecutionPolicy Bypass -File C:\saqr\_deploy_train.ps1", timeout=90))
c.close()
print("DONE")
