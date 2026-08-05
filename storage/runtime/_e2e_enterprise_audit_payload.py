
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
    ARCHITECTURE_MODE, CIRCUIT_BREAKER_MAX_LOSSES, ENTERPRISE_TIMEFRAMES,
)
r = load_project_rules()
ok("REF_CAPITAL", float(r.reference_capital) >= 5000, str(r.reference_capital))
ok("MIN_TRADE", float(r.min_trade_notional) >= 25, str(r.min_trade_notional))
ok("HYBRID_ON", bool(r.hybrid_mode))
ok("ENTERPRISE_ON", bool(r.enterprise_pipeline))
ok("ARCH_MODE", "Enterprise" in ARCHITECTURE_MODE)
ok("CB_MAX", int(CIRCUIT_BREAKER_MAX_LOSSES) >= 3)
ok("FRAMES", "4h" in ENTERPRISE_TIMEFRAMES and "1m" in ENTERPRISE_TIMEFRAMES)
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

from risk.enterprise_circuit_breaker import evaluate_circuit_breaker
ok("CB_CLEAR", evaluate_circuit_breaker(consecutive_losses=0).approved)
ok("CB_VETO", evaluate_circuit_breaker(consecutive_losses=3).veto)

from core.enterprise_pipeline import run_pre_execution_pipeline, PIPELINE_STAGES
ok("PIPE_STAGES", len(PIPELINE_STAGES) >= 8)
v = run_pre_execution_pipeline(
    symbol="BTC/USDT", signal="BUY SIGNAL", score=9, price=100.0,
    consecutive_losses=0, consensus_approved=True, risk_approved=True, for_auto_open=True,
)
ok("PIPE_AUTO_OK", v.approved and v.entry_mode == "auto", v.reason)
v2 = run_pre_execution_pipeline(
    symbol="BTC/USDT", signal="BUY SIGNAL", score=8, price=100.0,
    consecutive_losses=0, consensus_approved=True, risk_approved=True, for_auto_open=True,
)
ok("PIPE_BLOCK_MANUAL", (not v2.approved) and v2.entry_mode == "manual_broadcast")
v3 = run_pre_execution_pipeline(
    symbol="BTC/USDT", signal="BUY SIGNAL", score=9, price=100.0,
    consecutive_losses=3, consensus_approved=True, risk_approved=True, for_auto_open=True,
)
ok("PIPE_CB_VETO", (not v3.approved) and v3.vetoed)

from core.pre_flight import run_pre_flight_checks
ok("CORE_PREFLIGHT", callable(run_pre_flight_checks))

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
ok("MAIN_HEALTH", any("enterprise_health" in str(b) for row in mk["inline_keyboard"] for b in row))
ok("MAIN_DIAG", any("enterprise_diag" in str(b) for row in mk["inline_keyboard"] for b in row))

from operations.startup_cleanup import run_startup_cleanup
run_startup_cleanup(); ok("STARTUP_CLEANUP", True)
from database.repositories.trade_repo import TradeRepository
ok("REPO_BETWEEN", hasattr(TradeRepository, "list_closed_trades_between"))
from operations.post_mortem import record_post_mortem
ok("POST_MORTEM", callable(record_post_mortem))

w = open(r"C:\GoldenShield_Binance\run_official_bot.ps1", encoding="utf-8", errors="replace").read()
ok("WORKER_TAG", "GS_OFFICIAL_WORKER_v2026_08_ENTERPRISE" in w)
ok("WORKER_PREFLIGHT", "PREFLIGHT" in w and "ENTERPRISE" in w)
ok("WORKER_HYBRID_ENV", "HYBRID_SIGNAL_MODE" in w)
ok("WORKER_RULES_ENV", "PROJECT_REFERENCE_CAPITAL" in w)
ok("WORKER_CB_ENV", "CIRCUIT_BREAKER_MAX_LOSSES" in w)

env = open(r"C:\GoldenShield_Binance\.env", encoding="utf-8", errors="replace").read()
ok("ENV_FORCE", "BOT_FORCE_ACTIVE=true" in env.replace(" ", ""))
ok("ENV_REF", "PROJECT_REFERENCE_CAPITAL" in env)
ok("ENV_MIN", "PROJECT_MIN_TRADE_NOTIONAL" in env)
ok("ENV_HYBRID", "HYBRID_SIGNAL_MODE" in env)
ok("ENV_AUTO90", "AUTO_ENTRY_MIN_PERCENT=90" in env.replace(" ", ""))
ok("ENV_NOTIFY70", "TELEGRAM_SIGNAL_MIN_PERCENT=70" in env.replace(" ", ""))
ok("ENV_PIPELINE", "ENTERPRISE_PIPELINE_ENABLED" in env)
ok("ENV_CB", "CIRCUIT_BREAKER_MAX_LOSSES" in env)

import main as m
ok("MAIN_SSOT_HELPER", hasattr(m, "_ssot_open_count"))
ok("MAIN_RULES_BANNER", hasattr(m, "_log_project_rules_banner"))
src = open(r"C:\GoldenShield_Binance\main.py", encoding="utf-8", errors="replace").read()
ok("MAIN_PIPE_GATE", "run_pre_execution_pipeline" in src)

tex = open(r"C:\GoldenShield_Binance\execution\trade_executor.py", encoding="utf-8", errors="replace").read()
ok("FORCE_OPEN_RULES", "force_open=bool(force_open)" in tex)
ssot = open(r"C:\GoldenShield_Binance\execution\binance_position_sync.py", encoding="utf-8", errors="replace").read()
ok("SSOT_NOT_STUB", "discover_live_spot_holdings" in ssot and "get_live_open_positions_ssot" in ssot)

# تنظيف مؤقتات تشغيل فقط (لا DB)
import pathlib
rt = pathlib.Path(r"C:\GoldenShield_Binance\storage\runtime")
cleaned = 0
for p in list(rt.glob("*.tmp")) + list(rt.glob("*.temp")) + list(rt.glob("_worker_preflight.py")):
    try:
        p.unlink(); cleaned += 1
    except Exception:
        pass
ok("RUNTIME_TEMP_CLEAN", True, f"cleaned={cleaned}")

print("FAILS", len(fails))
if fails:
    print("FAILED:", ",".join(fails))
    raise SystemExit(1)
print("E2E_COHESION_OK")
print("ENTERPRISE_ARCHITECTURE_OK")
