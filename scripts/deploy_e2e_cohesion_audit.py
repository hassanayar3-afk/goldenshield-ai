"""Full E2E cohesion audit + hybrid rules deploy on VPS."""

from __future__ import annotations

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
    "run_official_bot.ps1",
    "run_official_bot.bat",
    "START_BOT.bat",
    "STOP_BOT.bat",
    "REST_BOT.bat",
    "main.py",
    "config/project_rules.py",
    "config/settings.py",
    "core/constants.py",
    "risk/lot_calculator.py",
    "execution/binance_position_sync.py",
    "execution/trade_executor.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_keyboards.py",
    "operations/telegram_commands.py",
    "operations/startup_cleanup.py",
    "operations/period_report.py",
    "operations/message_templates.py",
    "operations/signal_filter.py",
    "operations/dashboard_templates.py",
    "database/repositories/trade_repo.py",
    ".env.example",
]

AUDIT_PY = r'''
import os, sys, inspect
os.chdir(r"C:\GoldenShield_Binance")
sys.path.insert(0, r"C:\GoldenShield_Binance")
fails = []

def ok(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ((" " + detail) if detail else ""))
    if not cond:
        fails.append(name)

from config.project_rules import (
    load_project_rules, assert_entry_notional, compute_position_size,
    is_hybrid_auto_score, is_hybrid_manual_broadcast_score, hybrid_entry_label,
)
r = load_project_rules()
ok("REF_CAPITAL", float(r.reference_capital) >= 5000, str(r.reference_capital))
ok("MIN_TRADE", float(r.min_trade_notional) >= 25, str(r.min_trade_notional))
ok("HYBRID_ON", bool(r.hybrid_mode))
ok("HYBRID_AUTO_9", is_hybrid_auto_score(9) and is_hybrid_auto_score(10))
ok("HYBRID_MANUAL_78", is_hybrid_manual_broadcast_score(7) and is_hybrid_manual_broadcast_score(8))
ok("HYBRID_NOT_AUTO_8", not is_hybrid_auto_score(8))
ok("HYBRID_LABEL", "يدوي" in hybrid_entry_label(8) and "تلقائي" in hybrid_entry_label(9))
ok("DUST_REJECT", bool(assert_entry_notional(0.001, 10)))
ok("MANUAL_FORCE_LOOSE", assert_entry_notional(0.5, 20, force_open=True) == "")
amt,_,_,rej = compute_position_size(price=100.0, live_balance=5000.0)
ok("SIZE_OK", amt > 0 and not rej, f"amt={amt}")

from risk.lot_calculator import LotCalculator
ok("LOT_REJECT_DUST", LotCalculator(50.0).calculate(100.0)[0] == 0.0)

from operations.signal_filter import is_notifiable_trade_signal, entry_action_label
from types import SimpleNamespace
ok("NOTIFY_7", is_notifiable_trade_signal(SimpleNamespace(halted=False, signal="BUY SIGNAL", passed=True, score=7)))
ok("NOTIFY_8", is_notifiable_trade_signal(SimpleNamespace(halted=False, signal="BUY SIGNAL", passed=True, score=8)))
ok("NO_NOTIFY_6", not is_notifiable_trade_signal(SimpleNamespace(halted=False, signal="BUY SIGNAL", passed=True, score=6)))
ok("LABEL_MANUAL", "يدوي" in entry_action_label(8))
ok("LABEL_AUTO", "تلقائي" in entry_action_label(9))

from execution.binance_position_sync import get_live_open_positions_ssot, discover_live_spot_holdings
from operations.telegram_dashboard import TelegramDashboard
ok("SSOT_FN", callable(get_live_open_positions_ssot))
ok("DASH_SSOT", hasattr(TelegramDashboard, "_live_open_ssot"))
ok("MAIN_USES_SSOT", "_live_open_ssot" in inspect.getsource(TelegramDashboard.render_main))
ok("POS_USES_SSOT", "_live_open_ssot" in inspect.getsource(TelegramDashboard.render_positions))
ok("POS_NO_LOCAL_ALL", "position_manager.all()" not in inspect.getsource(TelegramDashboard.render_positions))
ok("HOLDINGS_FETCH", isinstance(discover_live_spot_holdings(), dict))

from operations.telegram_keyboards import close_menu_keyboard, report_period_keyboard, main_menu_keyboard
ck, rk, mk = close_menu_keyboard(), report_period_keyboard(), main_menu_keyboard(paused=False)
ok("CLOSE_MENU", any("close_winners" in str(b) for row in ck["inline_keyboard"] for b in row))
ok("CLOSE_LOSERS", any("close_losers" in str(b) for row in ck["inline_keyboard"] for b in row))
ok("CLOSE_ALL", any("close_all" in str(b) for row in ck["inline_keyboard"] for b in row))
ok("REPORT_WEEK", any("report_week" in str(b) for row in rk["inline_keyboard"] for b in row))
ok("REPORT_MONTH", any("report_month" in str(b) for row in rk["inline_keyboard"] for b in row))
ok("MAIN_CLOSE_SUB", any("close_menu" in str(b) for row in mk["inline_keyboard"] for b in row))

from operations.startup_cleanup import run_startup_cleanup
run_startup_cleanup(); ok("STARTUP_CLEANUP", True)
from database.repositories.trade_repo import TradeRepository
ok("REPO_BETWEEN", hasattr(TradeRepository, "list_closed_trades_between"))

w = open(r"C:\GoldenShield_Binance\run_official_bot.ps1", encoding="utf-8", errors="replace").read()
ok("WORKER_TAG", "GS_OFFICIAL_WORKER_v2026_08_HYBRID" in w)
ok("WORKER_PREFLIGHT", "PREFLIGHT" in w)
ok("WORKER_HYBRID_ENV", "HYBRID_SIGNAL_MODE" in w)
ok("WORKER_RULES_ENV", "PROJECT_REFERENCE_CAPITAL" in w)

env = open(r"C:\GoldenShield_Binance\.env", encoding="utf-8", errors="replace").read()
ok("ENV_FORCE", "BOT_FORCE_ACTIVE=true" in env.replace(" ", ""))
ok("ENV_REF", "PROJECT_REFERENCE_CAPITAL" in env)
ok("ENV_MIN", "PROJECT_MIN_TRADE_NOTIONAL" in env)
ok("ENV_HYBRID", "HYBRID_SIGNAL_MODE" in env)
ok("ENV_AUTO90", "AUTO_ENTRY_MIN_PERCENT=90" in env.replace(" ", ""))
ok("ENV_NOTIFY70", "TELEGRAM_SIGNAL_MIN_PERCENT=70" in env.replace(" ", ""))

import main as m
ok("MAIN_SSOT_HELPER", hasattr(m, "_ssot_open_count"))
ok("MAIN_RULES_BANNER", hasattr(m, "_log_project_rules_banner"))

tex = open(r"C:\GoldenShield_Binance\execution\trade_executor.py", encoding="utf-8", errors="replace").read()
ok("FORCE_OPEN_RULES", "force_open=bool(force_open)" in tex)

print("FAILS", len(fails))
if fails:
    print("FAILED:", ",".join(fails))
    raise SystemExit(1)
print("E2E_COHESION_OK")
'''

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$envp=Join-Path $g '.env'
$map=@{
  'BOT_FORCE_ACTIVE'='true'
  'HYBRID_SIGNAL_MODE'='true'
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='15'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='1'
  'PROJECT_REFERENCE_CAPITAL'='5000'
  'PROJECT_MIN_TRADE_NOTIONAL'='25'
  'PROJECT_MIN_EXCHANGE_NOTIONAL'='5'
  'AUTO_ENTRY_MIN_PERCENT'='90'
  'TELEGRAM_SIGNAL_MIN_PERCENT'='70'
  'MANUAL_ENTRY_REQUIRED'='false'
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
Write-Host 'ENV_RULES_SYNCED'

# استبدال العامل القديم بالكامل
Remove-Item (Join-Path $g 'run_official_bot.ps1.bak') -Force -EA SilentlyContinue

& $py 'C:\ProgramData\GoldenShield\_e2e_cohesion_audit.py'
if($LASTEXITCODE -ne 0){ Write-Host 'AUDIT_FAIL'; exit 1 }

$worker=Join-Path $g 'run_official_bot.ps1'
$tr = "powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$worker`""
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 2
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $tr /SC ONSTART /RL HIGHEST /F | Out-Null
try { $t=Get-ScheduledTask GoldenShieldBotOfficial; $t.Settings.Hidden=$true; $t.Settings.ExecutionTimeLimit='PT0S'; $t|Set-ScheduledTask|Out-Null } catch {}
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 16
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ('MAIN=' + $n)
if($n -ge 1){ Write-Host 'FULL_AUDIT_OK' } else { Write-Host 'FULL_AUDIT_CHECK' }
"""


def main() -> int:
    if not HOST or not USER or not PASSWORD:
        print("Set WIN_HOST / WIN_USER / WIN_PASSWORD")
        return 1
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    try:
        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            local = ROOT / rel
            if not local.is_file():
                print("MISSING", rel)
                continue
            sftp.put(str(local), f"{KEEP}/{rel}")
            print("UPLOADED", rel)
        with sftp.file(r"C:\ProgramData\GoldenShield\_e2e_cohesion_audit.py", "w") as fh:
            fh.write(AUDIT_PY)
        remote_ps = r"C:\ProgramData\GoldenShield\_deploy_e2e_audit.ps1"
        with sftp.file(remote_ps, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()
        _, o, e = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
            timeout=300,
        )
        out = (o.read() + e.read()).decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "FULL_AUDIT_OK" in out and "E2E_COHESION_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
