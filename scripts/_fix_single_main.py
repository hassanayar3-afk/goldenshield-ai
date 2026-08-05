import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
PS = r"""
$ErrorActionPreference='Continue'
$all=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' } | Sort-Object ProcessId)
Write-Output ('BEFORE=' + $all.Count)
if($all.Count -gt 1){
  $keep=$all[0]
  foreach($p in $all){ if($p.ProcessId -ne $keep.ProcessId){ Stop-Process -Id $p.ProcessId -Force -EA SilentlyContinue } }
  Start-Sleep -Seconds 2
}
if($all.Count -lt 1){
  schtasks /Run /TN 'GoldenShieldBotOfficial' | Out-Null
  Start-Sleep -Seconds 10
}
$all=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match 'main\.py' })
Write-Output ('MAIN=' + $all.Count)
"""
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(os.getenv("WIN_HOST"), username=os.getenv("WIN_USER"), password=os.getenv("WIN_PASSWORD"), timeout=45)
sftp = client.open_sftp()
path = r"C:\GoldenShield_Binance\storage\runtime\_fix_main.ps1"
with sftp.open(path, "w") as f:
    f.write(PS.encode("utf-8"))
sftp.close()
_i, o, e = client.exec_command(
    r'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\GoldenShield_Binance\storage\runtime\_fix_main.ps1"',
    timeout=60,
)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode("utf-8", errors="replace")
if err.strip():
    print(err[-800:])
client.close()
