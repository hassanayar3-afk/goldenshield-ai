"""مراقبة bot_stdout.log + أول Post-Mortem بعد إغلاق صفقة على VPS."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"
LOG = rf"{KEEP}\storage\logs\bot_stdout.log"
PM_DIR = rf"{KEEP}\storage\reports\post_mortem"
PM_INDEX = rf"{PM_DIR}\index.jsonl"


def _connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        os.getenv("WIN_HOST", "").strip(),
        username=os.getenv("WIN_USER", "").strip(),
        password=os.getenv("WIN_PASSWORD", ""),
        timeout=45,
    )
    return client


def _run(client: paramiko.SSHClient, cmd: str, timeout: int = 90) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def main() -> int:
    client = _connect()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"=== GoldenShield Monitor @ {now} ===\n")

    # 1) Process health
    ps = r"""
$mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.Name -match '^(python|pythonw|py)\.exe$' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
Write-Output ('MAIN=' + $mains.Count)
if(Test-Path 'C:\GoldenShield_Binance\run_official_bot.ps1'){
  $w=Get-Content 'C:\GoldenShield_Binance\run_official_bot.ps1' -Raw
  if($w -match 'GS_OFFICIAL_WORKER_v2026_08_ENTERPRISE'){ Write-Output 'WORKER=ENTERPRISE' }
}
"""
    code, out, err = _run(
        client,
        f'powershell -NoProfile -Command "{ps.replace(chr(10), "; ")}"',
        timeout=60,
    )
    print(out.strip() or "(no process output)")
    if err.strip():
        print("STDERR:", err[-800:])

    # 2) Tail bot_stdout.log
    tail_ps = rf"""
$log = '{LOG}'
if (Test-Path $log) {{
  $item = Get-Item $log
  Write-Output ('LOG_SIZE=' + $item.Length)
  Write-Output ('LOG_MOD=' + $item.LastWriteTime)
  Get-Content -Path $log -Tail 40 -Encoding UTF8
}} else {{
  Write-Output 'LOG_MISSING'
}}
"""
    sftp = client.open_sftp()
    ps_path = rf"{KEEP}\storage\runtime\_monitor_tail.ps1"
    with sftp.open(ps_path, "w") as f:
        f.write(tail_ps.encode("utf-8"))
    sftp.close()
    _code, log_tail, _err = _run(
        client,
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{ps_path}"',
        timeout=60,
    )
    print("\n--- bot_stdout.log (last 40 lines) ---")
    print(log_tail.strip() or "(empty)")

    # 3) Post-Mortem index / latest file
    pm_cmd = (
        rf'powershell -NoProfile -Command "'
        rf"$d='{PM_DIR}'; "
        rf"if(Test-Path $d){{ "
        rf"$files=Get-ChildItem $d -Filter 'pm_*.json' -EA SilentlyContinue | Sort-Object LastWriteTime -Descending; "
        rf"Write-Output ('PM_COUNT=' + $files.Count); "
        rf"if($files.Count -gt 0){{ $f=$files[0]; Write-Output ('PM_LATEST=' + $f.FullName); Get-Content $f.FullName -Raw -Encoding UTF8 }} "
        rf"}} else {{ Write-Output 'PM_DIR_MISSING' }}\""
    )
    _code, pm_out, _err = _run(client, pm_cmd, timeout=60)
    print("\n--- Post-Mortem ---")
    print(pm_out.strip() or "No post-mortem files yet (awaiting first close).")

    # 4) Quick grep for close events in recent log
    grep_cmd = (
        rf'powershell -NoProfile -Command "'
        rf"if(Test-Path '{LOG}'){{ "
        rf"Select-String -Path '{LOG}' -Pattern 'إغلاق|close|Post-Mortem|post_mortem|Take Profit|Stop Loss' -Encoding UTF8 | Select-Object -Last 8 | ForEach-Object {{ $_.Line }} "
        rf"}}\""
    )
    _code, close_hits, _err = _run(client, grep_cmd, timeout=60)
    if close_hits.strip():
        print("\n--- Recent close-related log lines ---")
        print(close_hits.strip())

    client.close()
    print("\n=== Monitor complete — awaiting first trade close for live Post-Mortem ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
