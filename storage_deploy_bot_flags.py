"""Deploy bot feature toggles to Saqr VPS."""
from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
import paramiko

FILES = [
    (r"C:\Users\acer\hassan\app\store.py", r"C:\saqr\app\store.py"),
    (r"C:\Users\acer\hassan\app\hidden_core\pipeline.py", r"C:\saqr\app\hidden_core\pipeline.py"),
    (r"C:\Users\acer\hassan\app\comments_responder.py", r"C:\saqr\app\comments_responder.py"),
    (r"C:\Users\acer\hassan\app\admin.py", r"C:\saqr\app\admin.py"),
    (r"C:\Users\acer\hassan\app\main.py", r"C:\saqr\app\main.py"),
    (r"C:\Users\acer\hassan\web\pages\settings.html", r"C:\saqr\web\pages\settings.html"),
    (r"C:\Users\acer\hassan\web\assets\js\pages\settings.js", r"C:\saqr\web\assets\js\pages\settings.js"),
    (r"C:\Users\acer\hassan\web\pages\bot-control.html", r"C:\saqr\web\pages\bot-control.html"),
    (r"C:\Users\acer\hassan\web\assets\js\pages\bot-control.js", r"C:\saqr\web\assets\js\pages\bot-control.js"),
    (r"C:\Users\acer\hassan\web\pages\training.html", r"C:\saqr\web\pages\training.html"),
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


smoke = r'''
import os
os.chdir(r"C:\saqr")
from app.store import ConversationStore
s = ConversationStore()
# ensure defaults on
s.set_bot_control(bot_enabled=True, dm_replies_enabled=True, comments_replies_enabled=True, snooze_until="")
ctrl = s.get_bot_control()
print("bot", ctrl.get("bot_enabled"), "dm", ctrl.get("dm_replies_enabled"), "comments", ctrl.get("comments_replies_enabled"))
print("dm_silenced", s.is_dm_reply_silenced(), "comments_silenced", s.is_comments_reply_silenced())
from app import main
print("ver", main.APP_VERSION)
'''
sftp = c.open_sftp()
with sftp.file(r"C:\saqr\_smoke_bot_flags.py", "w") as f:
    f.write(smoke)
sftp.close()
print(run(r"C:\saqr\.venv\Scripts\python.exe C:\saqr\_smoke_bot_flags.py"))

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
with sftp.file(r"C:\saqr\_restart285.ps1", "w") as f:
    f.write(ps)
sftp.close()
print(run(r"powershell -NoProfile -ExecutionPolicy Bypass -File C:\saqr\_restart285.ps1", timeout=90))
c.close()
print("DONE")
