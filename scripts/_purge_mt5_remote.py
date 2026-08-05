"""حذف بقايا MT5 من السيرفر + مزامنة ملفات Binance-only الحرجة."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

REMOTE = r"C:\GoldenShield_Binance"

DELETE_REL = [
    r"execution\mt5_bridge.py",
    r"data\mt5_market_data.py",
    r"data\forex_market_data.py",
    r"data\stock_market_data.py",
    r"config\mt5_symbol_map.yaml",
    r"docs\MT5_WINDOWS_SETUP.md",
    r"scripts\test_mt5_connect.py",
    r"tests\execution\test_mt5_bridge.py",
    r"tests\execution\test_order_manager_mt5_sl_tp.py",
    r"tests\data\test_forex_market_data.py",
    r"scripts\send_simple_windows_zip.py",
    r"scripts\send_windows_zip_telegram.py",
]

SYNC_REL = [
    "config/settings.py",
    "config/runtime_profile.py",
    "config/symbol_registry.yaml",
    "config/trial_params.yaml",
    "risk/iron_protocol.py",
    "execution/order_manager.py",
    "execution/trade_executor.py",
    "execution/sl_attachment_guard.py",
    "data/ohlcv_fetcher.py",
    "data/ticker_fetcher.py",
    "data/symbol_routing.py",
    "data/connection_monitor.py",
    "operations/symbol_registry.py",
    "operations/api_watchdog.py",
    "operations/pre_flight_checklist.py",
    "operations/telegram_admin.py",
    "operations/bot_admin.py",
    "operations/dashboard_templates.py",
    "main.py",
    ".env.example",
]

PS = r"""
$roots=@('C:\GoldenShield_Binance','C:\Users\Administrator\Downloads\GoldenShield')
foreach($bot in $roots){
  if(-not (Test-Path $bot)){ Write-Host ("SKIP missing "+$bot); continue }
  Write-Host ("CLEAN "+$bot)
  $del=@(
    'execution\mt5_bridge.py',
    'data\mt5_market_data.py',
    'data\forex_market_data.py',
    'data\stock_market_data.py',
    'config\mt5_symbol_map.yaml',
    'docs\MT5_WINDOWS_SETUP.md',
    'scripts\test_mt5_connect.py',
    'tests\execution\test_mt5_bridge.py',
    'tests\execution\test_order_manager_mt5_sl_tp.py',
    'tests\data\test_forex_market_data.py',
    'scripts\send_simple_windows_zip.py',
    'scripts\send_windows_zip_telegram.py'
  )
  foreach($r in $del){
    $p=Join-Path $bot $r
    if(Test-Path $p){ Remove-Item $p -Force; Write-Host ("DEL "+$bot+"\\"+$r) }
  }
  $envp=Join-Path $bot '.env'
  if(Test-Path $envp){
    $lines=Get-Content $envp -Encoding UTF8
    $out=@()
    foreach($line in $lines){
      if($line -match '^\s*(MT5_|BOT_AUTO_SYNC_MT5)\s*='){ continue }
      if($line -match '^\s*EXECUTION_BACKEND\s*='){ $out += 'EXECUTION_BACKEND=binance'; continue }
      $out += $line
    }
    if(-not ($out | Where-Object { $_ -match '^\s*EXECUTION_BACKEND\s*=' })){ $out += 'EXECUTION_BACKEND=binance' }
    $utf8=New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($envp, $out, $utf8)
    Write-Host ("ENV_SCRUBBED "+$bot)
  }
}
# مزامنة ملفات حرجة إلى Downloads أيضاً إن وُجدت
$src='C:\GoldenShield_Binance'
$dst='C:\Users\Administrator\Downloads\GoldenShield'
if((Test-Path $src) -and (Test-Path $dst)){
  $copy=@(
    'config\settings.py','config\runtime_profile.py','config\symbol_registry.yaml','config\trial_params.yaml',
    'risk\iron_protocol.py','execution\order_manager.py','execution\trade_executor.py','execution\sl_attachment_guard.py',
    'data\ohlcv_fetcher.py','data\ticker_fetcher.py','data\symbol_routing.py','data\connection_monitor.py',
    'operations\symbol_registry.py','operations\api_watchdog.py','operations\pre_flight_checklist.py',
    'operations\telegram_admin.py','operations\bot_admin.py','operations\dashboard_templates.py','main.py'
  )
  foreach($r in $copy){
    $from=Join-Path $src $r
    $to=Join-Path $dst $r
    if(Test-Path $from){
      $parent=Split-Path $to -Parent
      if(-not (Test-Path $parent)){ New-Item -ItemType Directory -Force -Path $parent | Out-Null }
      Copy-Item $from $to -Force
    }
  }
  Write-Host 'DOWNLOADS_SYNCED'
}
Write-Host 'ALL_ROOTS_CLEANED'

"""


def sftp_mkdirs(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = remote_dir.replace("/", "\\").split("\\")
    cur = parts[0] + "\\" if parts[0].endswith(":") else parts[0]
    for part in parts[1:]:
        if not part:
            continue
        cur = cur.rstrip("\\") + "\\" + part
        try:
            sftp.stat(cur)
        except OSError:
            try:
                sftp.mkdir(cur)
            except OSError:
                pass


def main() -> int:
    host = os.getenv("WIN_HOST")
    user = os.getenv("WIN_USER")
    password = os.getenv("WIN_PASSWORD")
    if not (host and user and password):
        print("missing WIN_*")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=45, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    for rel in SYNC_REL:
        local = ROOT / rel
        if not local.exists():
            print("SKIP", rel)
            continue
        remote = REMOTE + "\\" + rel.replace("/", "\\")
        sftp_mkdirs(sftp, str(Path(remote).parent))
        sftp.put(str(local), remote)
        print("UP", rel)
    sftp.close()

    remote_ps = r"C:\Users\Public\gs_purge_mt5.ps1"
    sftp = client.open_sftp()
    with sftp.file(remote_ps, "w") as fh:
        fh.write(PS)
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
        timeout=180,
    )
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    try:
        print(out)
    except UnicodeEncodeError:
        print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[-1500:])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
