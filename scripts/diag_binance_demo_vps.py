"""تشخيص سريع: لماذا لا تظهر صفقات/إشارات على Binance Demo."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    text = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
    print(text[-5000:].encode("ascii", "replace").decode("ascii"))
    return text


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )

    print("=== PROCESS ===")
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )

    print("=== ENV FLAGS (keys only values safe) ===")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Get-Content '{KEEP}\\.env' | Where-Object {{ $_ -match '^(EXECUTION_|BINANCE_DEMO|TELEGRAM_SIGNALS|MANUAL_ENTRY|AUTO_ENTRY|MAX_CONCURRENT)=' }}\"",
    )

    print("=== STOP FLAG ===")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Test-Path '{KEEP}\\storage\\runtime\\user_stopped.flag'; "
        f"if (Test-Path '{KEEP}\\storage\\runtime\\user_stopped.flag') {{ Get-Content '{KEEP}\\storage\\runtime\\user_stopped.flag' }}\"",
    )

    print("=== RECENT STDOUT ===")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"foreach($f in @('bot_stdout.log','stdout.log','operations.log','errors.log')){{ "
        f"$p=Join-Path '{KEEP}\\storage\\logs' $f; if(Test-Path $p){{ Write-Output ('==== '+$f); Get-Content $p -Tail 35 }} }}\"",
    )

    print("=== LIVE DIAGNOSTIC PYTHON ===")
    # لا تطبع مفاتيح API — فقط حالة الرصيد/الديمو/المراكز
    diag = r"""
import traceback
from config.settings import load_settings
s = load_settings(reload=True)
print('SETTINGS', {
  'mode': s.execution_mode,
  'backend': s.execution_backend,
  'demo': bool(getattr(s, 'binance_demo_trading', False)),
  'manual_entry': bool(getattr(s, 'manual_entry_required', False)),
  'auto_min': getattr(s, 'auto_entry_min_percent', None),
  'signals_only': bool(getattr(s, 'telegram_signals_only', False)),
  'has_key': bool(getattr(s, 'binance_api_key', None)),
  'has_secret': bool(getattr(s, 'binance_api_secret', None)),
})
try:
  from config.runtime_profile import resolve_runtime_profile
  p = resolve_runtime_profile(s)
  print('PROFILE', p)
except Exception as e:
  print('PROFILE_ERR', e)
try:
  from operations.symbol_registry import get_symbol_registry
  regs = get_symbol_registry()
  pairs = [x.id for x in regs.all_specs() if x.enabled]
  print('SYMBOLS_COUNT', len(pairs))
  print('SYMBOLS_SAMPLE', pairs[:20])
  print('HAS_FOREX', any(x.startswith('FOREX/') for x in pairs))
  print('HAS_STOCK', any(x.startswith('STOCK/') for x in pairs))
except Exception as e:
  print('SYMBOLS_ERR', e)
  traceback.print_exc()
try:
  import ccxt
  ex_kwargs = {'apiKey': s.binance_api_key, 'secret': s.binance_api_secret, 'enableRateLimit': True, 'options': {'defaultType': 'spot'}}
  if getattr(s, 'binance_demo_trading', False):
    ex = ccxt.binance(ex_kwargs)
    # demo endpoints used by project if any
    try:
      from data.binance_client import get_binance_exchange
      ex2 = get_binance_exchange()
      print('CLIENT', type(ex2).__name__, getattr(ex2, 'urls', {}).get('api', {}) if hasattr(ex2,'urls') else 'n/a')
      bal = ex2.fetch_balance()
    except Exception:
      # fallback raw
      if hasattr(ex, 'set_sandbox_mode'):
        try: ex.set_sandbox_mode(True)
        except Exception: pass
      # common demo host
      try:
        ex.urls['api'] = {
          'public': 'https://demo-api.binance.com/api/v3',
          'private': 'https://demo-api.binance.com/api/v3',
          'v1': 'https://demo-api.binance.com/api/v3',
        }
      except Exception:
        pass
      bal = ex.fetch_balance()
      ex2 = ex
  else:
    ex2 = ccxt.binance(ex_kwargs)
    bal = ex2.fetch_balance()
  usdt = (bal.get('USDT') or {})
  print('BALANCE_USDT', {k: usdt.get(k) for k in ('free','used','total')})
  totals = {k: v for k,v in (bal.get('total') or {}).items() if v and float(v) > 0}
  print('NONZERO_ASSETS', list(totals.items())[:15])
except Exception as e:
  print('BALANCE_ERR', type(e).__name__, e)
  traceback.print_exc()
try:
  from database.connection import get_connection
  # best effort open positions in local db
  import sqlite3
  db = getattr(s, 'db_path', 'storage/db/goldenshield.db')
  con = sqlite3.connect(db)
  cur = con.cursor()
  tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'").fetchall()]
  print('DB_TABLES', tables[:30])
  for t in tables:
    if 'trade' in t.lower() or 'position' in t.lower():
      try:
        n = cur.execute('select count(*) from %s' % t).fetchone()[0]
        print('TABLE', t, n)
      except Exception as e:
        print('TABLE_ERR', t, e)
  con.close()
except Exception as e:
  print('DB_ERR', e)
"""
    # write diag file remotely to avoid quoting hell
    remote = KEEP + r"\_diag_demo.py"
    sftp = ssh.open_sftp()
    with sftp.file(remote.replace("\\", "/"), "w") as f:
        f.write(diag)
    sftp.close()
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Set-Location '{KEEP}'; & '{PY}' _diag_demo.py\"",
        timeout=180,
    )

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
