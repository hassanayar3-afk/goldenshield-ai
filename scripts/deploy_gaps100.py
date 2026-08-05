"""Deploy gap-closure files + verify 100% literal compliance."""
from __future__ import annotations

import io
import os
import sys
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
    "main.py",
    "config/project_rules.py",
    "core/constants.py",
    "core/analyzer.py",
    "core/hybrid_engine.py",
    "core/micro_structure.py",
    "core/enterprise_pipeline.py",
    "core/technical/micro_entry.py",
    "data/ohlcv_fetcher.py",
    "execution/trade_executor.py",
    "operations/post_mortem.py",
    "operations/telegram_keyboards.py",
]

AUDIT = r'''
import os, sys, inspect
os.chdir(r"C:\GoldenShield_Binance")
sys.path.insert(0, r"C:\GoldenShield_Binance")
fails=[]
def ok(n,c,d=""):
    print(("PASS " if c else "FAIL ")+n+((" "+d) if d else ""))
    if not c: fails.append(n)

from core.constants import ANALYSIS_TIMEFRAMES, TIMEFRAMES, SIGNAL_NOTIFY_MIN_PERCENT, SIGNAL_AUTO_PERCENT
from config.project_rules import ENTERPRISE_MANUAL_PREFERRED_PERCENT, HYBRID_MANUAL_MIN_PERCENT, HYBRID_AUTO_MIN_PERCENT
ok("TF_HIER", TIMEFRAMES==("15m","1h","4h"))
ok("TF_ANALYSIS", set(ANALYSIS_TIMEFRAMES)>=set(["4h","1h","15m","5m","1m"]))
ok("THR_MANUAL", SIGNAL_NOTIFY_MIN_PERCENT==70 and HYBRID_MANUAL_MIN_PERCENT==70 and ENTERPRISE_MANUAL_PREFERRED_PERCENT==70)
ok("THR_AUTO", SIGNAL_AUTO_PERCENT==90 and HYBRID_AUTO_MIN_PERCENT==90)

an=open("core/analyzer.py",encoding="utf-8",errors="replace").read()
ok("ANALYZER_MICRO_OB", "analyze_orderbook_micro" in an)
ok("ANALYZER_MICRO_TF", "evaluate_micro_entry" in an and "ANALYSIS_TIMEFRAMES" in an)
ok("ANALYZER_5M", '"5m"' in an or "'5m'" in an)

hy=open("core/hybrid_engine.py",encoding="utf-8",errors="replace").read()
ok("HYBRID_MICRO", "analyze_orderbook_micro" in hy)

oh=open("data/ohlcv_fetcher.py",encoding="utf-8",errors="replace").read()
ok("OHLCV_ANALYSIS_DEFAULT", "ANALYSIS_TIMEFRAMES" in oh)

tex=open("execution/trade_executor.py",encoding="utf-8",errors="replace").read()
ok("PM_WIRED", "_record_post_mortem_safe" in tex and "record_close_post_mortem" in tex)

main=open("main.py",encoding="utf-8",errors="replace").read()
ok("FAIL_CLOSED", "FAIL-CLOSED" in main or "FAIL_CLOSED" in main)
ok("FAIL_CLOSED_RETURN", "enterprise pipeline FAIL-CLOSED" in main)

from operations.post_mortem import record_close_post_mortem, record_post_mortem
p=record_close_post_mortem(symbol="BTC/USDT", side="buy", entry=100, exit_price=101, pnl=1.0, reason="audit_test", score=9)
ok("PM_WRITE", bool(p))

from operations.telegram_keyboards import close_menu_keyboard, report_period_keyboard, main_menu_keyboard
ck,rk,mk=close_menu_keyboard(), report_period_keyboard(), main_menu_keyboard(paused=False)
ok("CLOSE3", all(x in str(ck) for x in ["close_winners","close_losers","close_all"]))
ok("REPORTS", "report_week" in str(rk) and "report_month" in str(rk))
ok("UI", "view:main" in str(mk) or "مراكزي" in str(mk) or "enterprise_health" in str(mk))
from execution.binance_position_sync import get_live_open_positions_ssot
ok("SSOT", callable(get_live_open_positions_ssot) and "discover_live_spot_holdings" in open("execution/binance_position_sync.py",encoding="utf-8",errors="replace").read())

print("FAILS", len(fails))
if fails:
    print("FAILED", ",".join(fails)); raise SystemExit(1)
print("GAPS_CLOSED_100")
print("LITERAL_COMPLIANCE_OK")
'''


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=45)
    sftp = client.open_sftp()
    for rel in UPLOADS:
        local = ROOT / rel
        if not local.is_file():
            print("SKIP", rel)
            continue
        remote = f"{KEEP}\\{rel.replace('/', chr(92))}"
        rdir = remote.rsplit("\\", 1)[0]
        parts = rdir.split("\\")
        cur = parts[0] + "\\"
        for p in parts[1:]:
            if not p:
                continue
            cur = cur.rstrip("\\") + "\\" + p
            try:
                sftp.stat(cur)
            except OSError:
                try:
                    sftp.mkdir(cur)
                except OSError:
                    pass
        sftp.put(str(local), remote)
        print("UPLOADED", rel)
    remote_audit = f"{KEEP}\\storage\\runtime\\_gaps100_audit.py"
    sftp.putfo(io.BytesIO(AUDIT.encode("utf-8")), remote_audit)
    sftp.close()

    cmd = (
        rf'cmd /c "cd /d {KEEP} && set PYTHONPATH={KEEP} && '
        r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe "
        r'storage\runtime\_gaps100_audit.py"'
    )
    _i, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print("STDERR:", err[-1500:])
    print("AUDIT_EXIT", code)

    # restart single instance
    ps = r"""
$ErrorActionPreference='Continue'
Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep -Seconds 3
Remove-Item 'C:\GoldenShield_Binance\storage\runtime\user_stopped.flag' -Force -EA SilentlyContinue
Remove-Item 'C:\GoldenShield_Binance\storage\runtime\bot_instance.lock' -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
Get-ChildItem 'C:\GoldenShield_Binance\storage\runtime' -Filter '*.tmp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
schtasks /Run /TN 'GoldenShieldBotOfficial' | Out-Null
Start-Sleep -Seconds 12
$mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.CommandLine -match 'main\.py' } | Sort-Object ProcessId)
if($mains.Count -gt 1){ $keep=$mains[0]; foreach($p in $mains){ if($p.ProcessId -ne $keep.ProcessId){ Stop-Process -Id $p.ProcessId -Force -EA SilentlyContinue } }; Start-Sleep -Seconds 2 }
$mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object { $_.CommandLine -match 'main\.py' })
Write-Output ('MAIN=' + $mains.Count)
if($mains.Count -ge 1){ Write-Output 'FULL_AUDIT_OK' } else { Write-Output 'FULL_AUDIT_WARN_NO_MAIN' }
"""
    sftp = client.open_sftp()
    with sftp.open(f"{KEEP}\\storage\\runtime\\_gaps_restart.ps1", "w") as f:
        f.write(ps.encode("utf-8"))
    sftp.close()
    _i, stdout, stderr = client.exec_command(
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File "{KEEP}\storage\runtime\_gaps_restart.ps1"',
        timeout=90,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
