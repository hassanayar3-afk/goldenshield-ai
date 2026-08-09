import paramiko,os,sys
from pathlib import Path
from dotenv import load_dotenv
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
load_dotenv(Path(".env"))
LOCAL=Path(r"C:\Users\acer\hassan")
files=[
 r"app\main.py",
 r"web\assets\js\ui.js",
 r"web\assets\js\app.js",
 r"web\assets\css\layout.css",
 r"web\assets\js\pages\notifications.js",
 r"web\assets\js\pages\campaigns.js",
 r"web\pages\notifications.html",
 r"web\service-worker.js",
]
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(os.environ["WIN_HOST"],username=os.environ["WIN_USER"],password=os.environ["WIN_PASSWORD"],timeout=25)
sftp=c.open_sftp()
for rel in files:
  sftp.put(str(LOCAL/rel), f"C:\\saqr\\{rel}"); print("PUT",rel)
sftp.close()
ps=r"""
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn app\.main:app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 2
if (Test-Path C:\saqr\storage\MANUAL_STOP.flag) { Remove-Item C:\saqr\storage\MANUAL_STOP.flag -Force }
powershell -NoProfile -ExecutionPolicy Bypass -File C:\saqr\ENSURE_BOT.ps1
Start-Sleep 5
curl.exe -s -m 10 http://127.0.0.1:8090/health
"""
sftp=c.open_sftp()
with sftp.file(r"C:\saqr\storage\_r.ps1","w") as f: f.write(ps)
sftp.close()
_,o,_=c.exec_command(r'powershell -NoProfile -ExecutionPolicy Bypass -File C:\saqr\storage\_r.ps1',timeout=90)
print(o.read().decode("utf-8","replace"))
c.close()
