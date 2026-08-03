"""نشر: يدوي بلا سقف عدد + تلقائي مقيد."""

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
UPLOADS = ["execution/trade_executor.py", "config/settings.py"]


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    try:
        def run(cmd: str, timeout: int = 180) -> str:
            _, o, e = ssh.exec_command(cmd, timeout=timeout)
            return (o.read() + e.read()).decode("utf-8", errors="replace")

        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            sftp.put(str(ROOT / rel), remote)
            print("UPLOADED", rel)
        sftp.close()
        ps = r"""
$good='C:\GoldenShield_Binance'
$envp=Join-Path $good '.env'
$map=@{ 'MANUAL_MAX_CONCURRENT_POSITIONS'='0'; 'MAX_CONCURRENT_POSITIONS'='12' }
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
Remove-Item (Join-Path $good 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 16
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ("MAIN="+$n)
if($n -eq 1){ Write-Host 'MANUAL_OPEN_OK' } else { Write-Host 'MANUAL_OPEN_CHECK' }
"""
        remote = r"C:\ProgramData\GoldenShield\manual_open.ps1"
        sftp = ssh.open_sftp()
        with sftp.file(remote, "w") as fh:
            fh.write(ps.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        out = run(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"', 240)
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "MANUAL_OPEN_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
