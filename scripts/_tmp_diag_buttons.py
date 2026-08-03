import os
import sys

import paramiko
from dotenv import load_dotenv

load_dotenv(".env", override=True)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(
    os.environ["WIN_HOST"],
    username=os.environ["WIN_USER"],
    password=os.environ["WIN_PASSWORD"],
    timeout=45,
    allow_agent=False,
    look_for_keys=False,
)
ps = r"""
$g='C:\GoldenShield_Binance'
Write-Host '=== MAIN ==='
$mains=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
Write-Host ('MAIN_COUNT=' + $mains.Count)
foreach($p in $mains){ Write-Host ('PID=' + $p.ProcessId + ' CMD=' + $p.CommandLine) }

Write-Host '=== ENV KEYS (names only) ==='
Select-String -Path (Join-Path $g '.env') -Pattern '^(TELEGRAM_|BOT_FORCE|EXECUTION_|BINANCE_DEMO|LOOP_|MANUAL_)' | ForEach-Object {
  $line=$_.Line
  if($line -match '^(.*?)='){ 
    $k=$Matches[1]
    $has = if($line -match '=.+$'){'SET'}else{'EMPTY'}
    Write-Host ($k + '=' + $has)
  }
}

Write-Host '=== LOG TAIL ==='
$log=Join-Path $g 'storage\logs\bot_stdout.log'
if(Test-Path $log){ Get-Content $log -Tail 40 -Encoding UTF8 }

Write-Host '=== ERROR LOG ==='
$err=Join-Path $g 'storage\logs'
Get-ChildItem $err -Filter '*error*' -EA SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object {
  Write-Host ('FILE=' + $_.Name)
  Get-Content $_.FullName -Tail 20 -EA SilentlyContinue
}
"""
remote = r"C:\ProgramData\GoldenShield\_diag_buttons.ps1"
sftp = ssh.open_sftp()
with sftp.file(remote, "w") as fh:
    fh.write(ps.replace("\r\n", "\n").replace("\n", "\r\n"))
sftp.close()
_, o, e = ssh.exec_command(
    f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', timeout=90
)
print((o.read() + e.read()).decode("utf-8", "replace"))
ssh.close()
