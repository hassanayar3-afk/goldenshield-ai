
import os, sys
os.chdir(r"C:\GoldenShield_Binance")
sys.path.insert(0, r"C:\GoldenShield_Binance")
fails = []
def ok(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + ((" " + d) if d else ""))
    if not c: fails.append(n)

from config.project_rules import load_project_rules, ARCHITECTURE_MODE, CIRCUIT_BREAKER_MAX_LOSSES
from core.enterprise_pipeline import PIPELINE_STAGES, run_pre_execution_pipeline
from risk.enterprise_circuit_breaker import evaluate_circuit_breaker
from operations.telegram_keyboards import main_menu_keyboard, close_menu_keyboard, report_period_keyboard
from execution.binance_position_sync import get_live_open_positions_ssot, discover_live_spot_holdings

r = load_project_rules()
ok("REF", float(r.reference_capital) >= 5000)
ok("MIN", float(r.min_trade_notional) >= 25)
ok("HYBRID", r.hybrid_mode)
ok("ENTERPRISE", r.enterprise_pipeline)
ok("ARCH", "Enterprise" in ARCHITECTURE_MODE)
ok("CB", CIRCUIT_BREAKER_MAX_LOSSES >= 3)
ok("STAGES", len(PIPELINE_STAGES) >= 8)
v = run_pre_execution_pipeline(symbol="BTC/USDT", signal="BUY SIGNAL", score=9, price=100.0, consecutive_losses=0, consensus_approved=True, risk_approved=True)
ok("PIPE_AUTO", v.approved and v.entry_mode == "auto", v.reason)
v2 = run_pre_execution_pipeline(symbol="BTC/USDT", signal="BUY SIGNAL", score=8, price=100.0, consecutive_losses=0, consensus_approved=True, risk_approved=True)
ok("PIPE_MANUAL", (not v2.approved) and v2.entry_mode == "manual_broadcast")
ok("CB_VETO", evaluate_circuit_breaker(consecutive_losses=3).veto)
mk = main_menu_keyboard(paused=False)
ck = close_menu_keyboard()
rk = report_period_keyboard()
ok("CLOSE", any("close_winners" in str(b) for row in ck["inline_keyboard"] for b in row))
ok("REPORT", any("report_week" in str(b) for row in rk["inline_keyboard"] for b in row))
ok("HEALTH", any("enterprise_health" in str(b) for row in mk["inline_keyboard"] for b in row))
ok("SSOT", callable(get_live_open_positions_ssot) and "discover_live_spot_holdings" in open("execution/binance_position_sync.py", encoding="utf-8", errors="replace").read())
w = open("run_official_bot.ps1", encoding="utf-8", errors="replace").read()
ok("WORKER", "GS_OFFICIAL_WORKER_v2026_08_ENTERPRISE" in w)
env = open(".env", encoding="utf-8", errors="replace").read()
ok("ENV_PIPE", "ENTERPRISE_PIPELINE_ENABLED" in env)
ok("ENV_CB", "CIRCUIT_BREAKER_MAX_LOSSES" in env)
src = open("main.py", encoding="utf-8", errors="replace").read()
ok("MAIN_PIPE", "run_pre_execution_pipeline" in src)
print("FAILS", len(fails))
if fails:
    print("FAILED", ",".join(fails))
    raise SystemExit(1)
print("E2E_COHESION_OK")
print("ENTERPRISE_ARCHITECTURE_OK")
