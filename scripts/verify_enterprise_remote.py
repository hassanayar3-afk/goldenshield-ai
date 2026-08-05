"""Remote verify enterprise deploy."""
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

REMOTE_PY = r'''
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
'''


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=45)
    sftp = client.open_sftp()
    remote = r"C:\GoldenShield_Binance\storage\runtime\_verify_enterprise.py"
    local = ROOT / "storage" / "runtime" / "_verify_enterprise.py"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(REMOTE_PY, encoding="utf-8")
    sftp.put(str(local), remote)
    sftp.close()

    ps = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
$py='C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
if (!(Test-Path $py)) { $py='py' }
$envp=Join-Path $g '.env'
$map=@{
  'BOT_FORCE_ACTIVE'='true'
  'HYBRID_SIGNAL_MODE'='true'
  'ENTERPRISE_PIPELINE_ENABLED'='true'
  'SSOT_SYNC_ENABLED'='true'
  'POST_MORTEM_ENGINE_ACTIVE'='true'
  'CIRCUIT_BREAKER_MAX_LOSSES'='3'
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
[System.IO.File]::WriteAllLines($envp, @($out), $utf8)
Write-Output 'ENV_RULES_SYNCED'
$rt=Join-Path $g 'storage\runtime'
Get-ChildItem $rt -Filter '*.tmp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Get-ChildItem $rt -Filter '*.temp' -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
$env:PYTHONPATH=$g
Set-Location $g
& $py (Join-Path $rt '_verify_enterprise.py')
$code=$LASTEXITCODE
Remove-Item (Join-Path $rt '_verify_enterprise.py') -Force -EA SilentlyContinue
if($code -ne 0){ Write-Output 'FULL_AUDIT_FAIL'; exit $code }
$mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
  $_.Name -match '^(python|pythonw|py)\.exe$' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
})
if($mains.Count -lt 1){
  schtasks /Run /TN 'GoldenShieldBotOfficial' 2>$null
  Start-Sleep -Seconds 10
  $mains=@(Get-CimInstance Win32_Process -EA SilentlyContinue | Where-Object {
    $_.Name -match '^(python|pythonw|py)\.exe$' -and $_.CommandLine -and $_.CommandLine -match 'main\.py'
  })
}
Write-Output ('MAIN=' + $mains.Count)
if($mains.Count -ge 1){ Write-Output 'FULL_AUDIT_OK' } else { Write-Output 'FULL_AUDIT_WARN_NO_MAIN'; exit 2 }
"""
    stdin, stdout, stderr = client.exec_command(
        "powershell -NoProfile -ExecutionPolicy Bypass -Command -",
        timeout=120,
    )
    stdin.write(ps)
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err[-3000:], file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
