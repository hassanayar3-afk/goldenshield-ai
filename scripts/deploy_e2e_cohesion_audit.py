"""Full E2E cohesion audit + deploy conversation rules on VPS."""

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
    "risk/lot_calculator.py",
    "execution/binance_position_sync.py",
    "execution/trade_executor.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_keyboards.py",
    "operations/telegram_commands.py",
    "operations/startup_cleanup.py",
    "operations/period_report.py",
    "operations/message_templates.py",
    "database/repositories/trade_repo.py",
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

# 1 rules
from config.project_rules import load_project_rules, assert_entry_notional, compute_position_size
r = load_project_rules()
ok("REF_CAPITAL", float(r.reference_capital) >= 5000, str(r.reference_capital))
ok("MIN_TRADE", float(r.min_trade_notional) >= 25, str(r.min_trade_notional))
ok("DUST_REJECT", bool(assert_entry_notional(0.001, 10)))
amt,_,_,rej = compute_position_size(price=100.0, live_balance=5000.0)
ok("SIZE_OK", amt > 0 and not rej, f"amt={amt}")

# 2 lot
from risk.lot_calculator import LotCalculator
a,_,_ = LotCalculator(50.0).calculate(100.0)
ok("LOT_REJECT_DUST", a == 0.0)

# 3 SSoT
from execution.binance_position_sync import get_live_open_positions_ssot, discover_live_spot_holdings
from operations.telegram_dashboard import TelegramDashboard
ok("SSOT_FN", callable(get_live_open_positions_ssot))
ok("DASH_SSOT", hasattr(TelegramDashboard, "_live_open_ssot"))
sm = inspect.getsource(TelegramDashboard.render_main)
sp = inspect.getsource(TelegramDashboard.render_positions)
ok("MAIN_USES_SSOT", "_live_open_ssot" in sm)
ok("POS_USES_SSOT", "_live_open_ssot" in sp)
ok("POS_NO_LOCAL_ALL", "position_manager.all()" not in sp)
h = discover_live_spot_holdings()
ok("HOLDINGS_FETCH", isinstance(h, dict), f"n={len(h)}")

# 4 UI
from operations.telegram_keyboards import close_menu_keyboard, report_period_keyboard, main_menu_keyboard
ck = close_menu_keyboard()
rk = report_period_keyboard()
mk = main_menu_keyboard(paused=False)
ok("CLOSE_MENU", any("close_winners" in str(b) for row in ck["inline_keyboard"] for b in row))
ok("CLOSE_LOSERS", any("close_losers" in str(b) for row in ck["inline_keyboard"] for b in row))
ok("CLOSE_ALL", any("close_all" in str(b) for row in ck["inline_keyboard"] for b in row))
ok("REPORT_WEEK", any("report_week" in str(b) for row in rk["inline_keyboard"] for b in row))
ok("REPORT_MONTH", any("report_month" in str(b) for row in rk["inline_keyboard"] for b in row))
ok("MAIN_CLOSE_SUB", any("close_menu" in str(b) for row in mk["inline_keyboard"] for b in row))

# 5 startup + repo
from operations.startup_cleanup import run_startup_cleanup
run_startup_cleanup()
ok("STARTUP_CLEANUP", True)
from database.repositories.trade_repo import TradeRepository
ok("REPO_BETWEEN", hasattr(TradeRepository, "list_closed_trades_between"))

# 6 launcher tag
w = open(r"C:\GoldenShield_Binance\run_official_bot.ps1", encoding="utf-8", errors="replace").read()
ok("WORKER_TAG", "GS_OFFICIAL_WORKER_v2026_08_1" in w)
ok("WORKER_PREFLIGHT", "Invoke-ConversationRulesPreflight" in w or "PREFLIGHT" in w)
ok("WORKER_RULES_ENV", "PROJECT_REFERENCE_CAPITAL" in w and "5000" in w)

# 7 env
env = open(r"C:\GoldenShield_Binance\.env", encoding="utf-8", errors="replace").read()
ok("ENV_FORCE", "BOT_FORCE_ACTIVE=true" in env.replace(" ", ""))
ok("ENV_REF", "PROJECT_REFERENCE_CAPITAL" in env)
ok("ENV_MIN", "PROJECT_MIN_TRADE_NOTIONAL" in env)

# 8 main helpers
import main as m
ok("MAIN_SSOT_HELPER", hasattr(m, "_ssot_open_count"))
ok("MAIN_RULES_BANNER", hasattr(m, "_log_project_rules_banner"))

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

# ensure env rules
$envp=Join-Path $g '.env'
$map=@{
  'BOT_FORCE_ACTIVE'='true'
  'TELEGRAM_LIVE_SIGNALS'='true'
  'TELEGRAM_LIVE_SIGNALS_SECONDS'='15'
  'TELEGRAM_LIVE_POSITIONS_SECONDS'='1'
  'PROJECT_REFERENCE_CAPITAL'='5000'
  'PROJECT_MIN_TRADE_NOTIONAL'='25'
  'PROJECT_MIN_EXCHANGE_NOTIONAL'='5'
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

& $py 'C:\ProgramData\GoldenShield\_e2e_cohesion_audit.py'
if($LASTEXITCODE -ne 0){ Write-Host 'AUDIT_FAIL'; exit 1 }

# re-register task to new worker
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
$trLine=(schtasks /Query /TN GoldenShieldBotOfficial /FO LIST /V 2>$null | Select-String 'Task To Run').ToString()
Write-Host ('TASK=' + $trLine)
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
