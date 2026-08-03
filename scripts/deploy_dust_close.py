"""Deploy dust-close fix, restart, and close all dust opens once."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"

CLOSE_PY = r'''
import os, sys
os.chdir(r"C:\GoldenShield_Binance")
sys.path.insert(0, r"C:\GoldenShield_Binance")
from config.settings import load_settings
from database.connection import init_database
from database.repositories.trade_repo import TradeRepository
from execution.trade_executor import TradeExecutor
from data.exchange_client import get_exchange

s = load_settings(reload=True)
db = init_database(s.db_path)
repo = TradeRepository(db)
ex = TradeExecutor(trade_repository=repo)
n = ex.restore_open_positions()
print("RESTORED", n)
print("OPEN_BEFORE", ex.position_manager.count())
exch = get_exchange()
for pos in list(ex.position_manager.all()):
    try:
        t = exch.fetch_ticker(pos.symbol)
        px = float(t.get("last") or t.get("close") or pos.entry_price)
        ok = ex.close_position(pos.symbol, px, reason="تنظيف غبار Spot")
        print("CLOSED", pos.symbol, ok)
    except Exception as e:
        print("FAIL", pos.symbol, type(e).__name__, e)

left = list(repo.list_open_trades() or [])
print("OPEN_AFTER", len(left))
for r in left:
    print("LEFT", r.symbol, r.amount)
'''

PS = r"""
$g='C:\GoldenShield_Binance'
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 2
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe' 'C:\ProgramData\GoldenShield\_close_dust_once.py'
Write-Host 'DUST_CLOSE_DONE'
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 8
$m=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' })
Write-Host ('MAIN=' + $m.Count)
"""

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(os.environ["WIN_HOST"], username=os.environ["WIN_USER"], password=os.environ["WIN_PASSWORD"], timeout=45, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    sftp.put(str(ROOT / "execution/trade_executor.py"), KEEP + r"\execution\trade_executor.py")
    print("UP trade_executor.py")
    with sftp.file(r"C:\ProgramData\GoldenShield\_close_dust_once.py", "w") as fh:
        fh.write(CLOSE_PY)
    with sftp.file(r"C:\ProgramData\GoldenShield\_deploy_dust_close.ps1", "w") as fh:
        fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
    sftp.close()
    _, o, e = ssh.exec_command(
        r'powershell -NoProfile -ExecutionPolicy Bypass -File "C:\ProgramData\GoldenShield\_deploy_dust_close.ps1"',
        timeout=180,
    )
    print((o.read() + e.read()).decode("utf-8", "replace"))
    ssh.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
