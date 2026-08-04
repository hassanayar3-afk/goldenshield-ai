"""نشر طبقات التحكم المضافة إلى C:\\GoldenShield_Binance + إعادة تشغيل المهمة."""

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
    "config/project_rules.py",
    "operations/startup_cleanup.py",
    "operations/period_report.py",
    "operations/dashboard_templates.py",
    "operations/message_templates.py",
    "operations/telegram_keyboards.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_commands.py",
    "database/repositories/trade_repo.py",
    "execution/trade_executor.py",
    "risk/lot_calculator.py",
    "main.py",
    ".env.example",
]

VERIFY_PY = r'''
import os, sys
os.chdir(r"C:\GoldenShield_Binance")
sys.path.insert(0, r"C:\GoldenShield_Binance")
from config.project_rules import load_project_rules, assert_entry_notional
from operations.telegram_keyboards import close_menu_keyboard, report_period_keyboard, main_menu_keyboard
from operations.period_report import period_bounds
from database.repositories.trade_repo import TradeRepository

r = load_project_rules()
assert float(r.reference_capital) >= 5000
assert assert_entry_notional(0.001, 10)
ck = close_menu_keyboard()
assert any("close_winners" in str(b) for row in ck["inline_keyboard"] for b in row)
rk = report_period_keyboard()
assert any("report_week" in str(b) for row in rk["inline_keyboard"] for b in row)
mk = main_menu_keyboard(paused=False)
assert any("close_menu" in str(b) for row in mk["inline_keyboard"] for b in row)
print("VERIFY_OK", "week", "ref", r.reference_capital, "min", r.min_trade_notional)
'''

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
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
Write-Host 'ENV_POLISH_OK'
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe' 'C:\ProgramData\GoldenShield\_verify_additive_polish.py'
if($LASTEXITCODE -ne 0){ Write-Host 'VERIFY_FAIL'; exit 1 }
schtasks /End /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py|run_official_bot' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
Start-Sleep 2
Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue
Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue
Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue
schtasks /Run /TN GoldenShieldBotOfficial | Out-Null
Start-Sleep 14
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ('MAIN=' + $n)
if($n -ge 1){ Write-Host 'ADDITIVE_POLISH_OK' } else { Write-Host 'ADDITIVE_POLISH_CHECK' }
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
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            # تأكد من المجلد البعيد
            remote_dir = remote.rsplit("\\", 1)[0]
            try:
                sftp.stat(remote_dir.replace("\\", "/"))
            except OSError:
                # إنشاء متداخل بسيط
                parts = remote_dir.replace("/", "\\").split("\\")
                cur = parts[0]
                for p in parts[1:]:
                    cur = cur + "\\" + p
                    try:
                        sftp.mkdir(cur.replace("\\", "/"))
                    except OSError:
                        pass
            sftp.put(str(local), remote.replace("\\", "/"))
            print("UPLOADED", rel)

        with sftp.file(r"C:\ProgramData\GoldenShield\_verify_additive_polish.py", "w") as fh:
            fh.write(VERIFY_PY)
        remote_ps = r"C:\ProgramData\GoldenShield\_deploy_additive_polish.ps1"
        with sftp.file(remote_ps, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()

        _, o, e = ssh.exec_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"',
            timeout=240,
        )
        out = (o.read() + e.read()).decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "ADDITIVE_POLISH_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
