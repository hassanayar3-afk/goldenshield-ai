"""نشر استراتيجية الربح الجزئي إلى VPS."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
HOST = os.getenv("WIN_HOST", "").strip()
USER = os.getenv("WIN_USER", "").strip()
PASSWORD = os.getenv("WIN_PASSWORD", "")
KEEP = r"C:\GoldenShield_Binance"
UPLOADS = [
    "execution/smart_exits.py",
    "execution/position_manager.py",
    "execution/trade_executor.py",
    "config/risk_params.yaml",
]

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$envp=Join-Path $g '.env'
$map=@{
  'PARTIAL_TP_ENABLED'='true'
  'PARTIAL_TP1_PCT'='0.50'
  'PARTIAL_TP2_PCT'='0.30'
  'PARTIAL_TP3_PCT'='0.20'
  'PARTIAL_TP1_R'='1.0'
  'PARTIAL_TP2_R'='2.0'
  'PARTIAL_TP3_R'='3.0'
  'PARTIAL_TP3_CLOSE_ENABLED'='true'
  'PARTIAL_TP_TRAIL_ENABLED'='true'
}
$lines=Get-Content $envp -EA SilentlyContinue
$keys=@{}
$out=foreach($line in $lines){
  if($line -match '^\s*#' -or $line -notmatch '='){ $line; continue }
  $k=($line -split '=',2)[0].Trim()
  if($map.ContainsKey($k)){ "$k=$($map[$k])"; $keys[$k]=1 } else { $line }
}
foreach($k in $map.Keys){ if(-not $keys.ContainsKey($k)){ $out += "$k=$($map[$k])" } }
$utf8=New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllLines($envp,$out,$utf8)
Write-Host 'ENV_OK'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Start-Sleep 3
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 16
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ('MAIN=' + $n)
if($n -eq 1){ Write-Host 'PARTIAL_TP_OK' } else { Write-Host 'PARTIAL_TP_CHECK' }
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    try:
        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            sftp.put(str(ROOT / rel), f"{KEEP}\\{rel.replace('/', '\\')}")
            print("UPLOADED", rel)
        remote = r"C:\ProgramData\GoldenShield\deploy_partial_tp.ps1"
        with sftp.file(remote, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        _, o, e = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
            timeout=240,
        )
        out = (o.read() + e.read()).decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "PARTIAL_TP_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
