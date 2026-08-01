"""افحص لماذا خرج البوت وأعد تشغيله من المسار الرسمي."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

PS = r"""
$ErrorActionPreference = 'Continue'
$good = 'C:\GoldenShield_Binance'
Set-Location $good
Write-Host '=== TAIL STDOUT ==='
if (Test-Path 'storage\logs\bot_stdout.log') { Get-Content 'storage\logs\bot_stdout.log' -Tail 60 }
Write-Host '=== TAIL ERR ==='
Get-ChildItem 'storage\logs' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 8 | ForEach-Object { Write-Host $_.FullName $_.LastWriteTime }
$errCandidates = @(
  'storage\logs\cmd_startup_err.txt',
  'storage\logs\bot_stderr.log',
  'storage\logs\goldenshield.log'
)
foreach ($f in $errCandidates) {
  if (Test-Path $f) {
    Write-Host ("=== FILE " + $f + " ===")
    Get-Content $f -Tail 40 -ErrorAction SilentlyContinue
  }
}

# أعد التشغيل مع لقطة
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
Remove-Item 'storage\runtime\user_stopped.flag' -Force -EA SilentlyContinue
Remove-Item 'storage\runtime\bot_instance.lock' -Force -EA SilentlyContinue
$out = 'storage\logs\boot_capture_out.txt'
$err = 'storage\logs\boot_capture_err.txt'
Remove-Item $out,$err -Force -EA SilentlyContinue
$p = Start-Process -FilePath $py -ArgumentList '-u','main.py' -WorkingDirectory $good -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 25
Write-Host ('STARTED_PID=' + $p.Id + ' HAS_EXITED=' + $p.HasExited)
if ($p.HasExited) { Write-Host ('EXIT_CODE=' + $p.ExitCode) }
Write-Host '=== BOOT OUT ==='
Get-Content $out -Tail 50 -EA SilentlyContinue
Write-Host '=== BOOT ERR ==='
Get-Content $err -Tail 50 -EA SilentlyContinue
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'main\.py') })
Write-Host ('BOT_PROCS=' + $procs.Count)
foreach ($x in $procs) { Write-Host ('PID=' + $x.ProcessId); Write-Host $x.CommandLine }
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.getenv("WIN_HOST"),
        username=os.getenv("WIN_USER"),
        password=os.getenv("WIN_PASSWORD"),
        timeout=40,
        allow_agent=False,
        look_for_keys=False,
    )
    remote = r"C:\Users\Public\gs_boot_debug.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote}"',
        timeout=120,
    )
    print(stdout.read().decode("utf-8", "replace"))
    err = stderr.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err[-1500:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
