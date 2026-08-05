"""فحص شامل: السيرفر + البوت + باينانس + أسباب التوقف/تسجيل الخروج."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

HOST = os.environ.get("WIN_HOST", "")
USER = os.environ.get("WIN_USER", "")
PASSWORD = os.environ.get("WIN_PASSWORD", "")
KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    text = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
    safe = text[-4500:].encode("ascii", "replace").decode("ascii")
    print(f"\n$ {cmd[:140]}\n{safe}")
    return text


def main() -> int:
    if not (HOST and USER and PASSWORD):
        print("NO_WIN_CREDENTIALS")
        return 1

    print("CONNECTING", HOST)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(
            HOST,
            username=USER,
            password=PASSWORD,
            timeout=45,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as exc:
        print("SSH_FAIL", type(exc).__name__, exc)
        print("LIKELY: Contabo VPS down / expired / network / wrong password")
        return 2

    print("SSH_OK")

    # 1) System / uptime / disk
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Write-Output ('COMPUTER='+$env:COMPUTERNAME); "
        "Write-Output ('NOW='+(Get-Date)); "
        "Write-Output ('UPTIME_DAYS='+((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalDays); "
        "Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free | Format-Table -AutoSize\"",
    )

    # 2) Bot process
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py|GoldenShield' } | "
        "Select-Object ProcessId,Name,CommandLine | Format-List\"",
    )

    # 3) Paths exist
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Write-Output ('BINANCE_PKG='+(Test-Path '{KEEP}\\main.py')); "
        "Write-Output ('GSBOT='+(Test-Path 'C:\\GSBot\\main.py')); "
        "Write-Output ('OLD_GOLDEN='+(Test-Path 'C:\\GoldenShield\\main.py')); "
        "Write-Output ('CONTABO_OLD='+(Test-Path 'C:\\Users\\Administrator\\Downloads\\Telegram Desktop\\GoldenShield_CONTABO_DEMO_20260728_2227\\main.py'))\"",
    )

    # 4) Stop flag / runtime
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"New-Item -ItemType Directory -Force -Path '{KEEP}\\storage\\runtime','{KEEP}\\storage\\logs' | Out-Null; "
        f"Write-Output ('STOP_FLAG='+(Test-Path '{KEEP}\\storage\\runtime\\user_stopped.flag')); "
        f"if (Test-Path '{KEEP}\\storage\\runtime\\user_stopped.flag') {{ Get-Content '{KEEP}\\storage\\runtime\\user_stopped.flag' }}; "
        f"Get-ChildItem '{KEEP}\\storage\\runtime' -EA SilentlyContinue | Select-Object Name,LastWriteTime,Length\"",
    )

    # 5) Scheduled task
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"schtasks /Query /TN GoldenShieldBotOfficial /V /FO LIST 2>&1 | Select-String -Pattern 'Task Name|Status|Last Run|Next Run|Task To Run|Last Result'\"",
    )

    # 6) Env flags (no secrets)
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Get-Content '{KEEP}\\.env' -EA SilentlyContinue | Where-Object {{ $_ -match '^(EXECUTION_MODE|EXECUTION_BACKEND|BINANCE_DEMO_TRADING|TELEGRAM_SIGNALS_ONLY|TELEGRAM_SEND_CYCLE_SIGNALS|AUTO_ENTRY_MIN_PERCENT|MANUAL_ENTRY_REQUIRED|NO_SLEEP_MODE|LOOP_INTERVAL_SECONDS|TELEGRAM_LIVE_SIGNALS_SECONDS)=' }}\"",
    )

    # 7) Recent logs
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Get-ChildItem '{KEEP}\\storage\\logs' -EA SilentlyContinue | Sort-Object LastWriteTime -Desc | Select-Object -First 10 Name,Length,LastWriteTime | Format-Table -AutoSize; "
        f"foreach ($f in @('bot_stdout.log','stdout.log','errors.log','operations.log')) {{ "
        f"$p=Join-Path '{KEEP}\\storage\\logs' $f; if (Test-Path $p) {{ Write-Output ('==== '+$f); Get-Content $p -Tail 25 }} }}\"",
    )

    # 8) Event log: unexpected shutdown / RDP logoff
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Write-Output '--- SYSTEM EVENTS ---'; "
        "Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074,6006,6008,41,7001,7002; StartTime=(Get-Date).AddDays(-3)} -MaxEvents 15 -EA SilentlyContinue | "
        "Select-Object TimeCreated,Id,ProviderName | Format-Table -AutoSize; "
        "Write-Output '--- RDP/LOGON ---'; "
        "Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624,4634,4647; StartTime=(Get-Date).AddDays(-2)} -MaxEvents 10 -EA SilentlyContinue | "
        "Select-Object TimeCreated,Id | Format-Table -AutoSize\"",
        timeout=180,
    )

    # 9) Python diag: settings + binance balance
    diag = r"""
from pathlib import Path
from config.settings import load_settings
s = load_settings(reload=True)
print('mode', s.execution_mode)
print('backend', s.execution_backend)
print('demo', bool(getattr(s,'binance_demo_trading', False)))
print('has_key', bool(getattr(s,'binance_api_key',None)))
print('has_secret', bool(getattr(s,'binance_api_secret',None)))
print('has_tg', bool(getattr(s,'telegram_token',None)))
print('pairs', len(getattr(s,'trading_pairs',[]) or []))
print('stop', Path('storage/runtime/user_stopped.flag').exists())
try:
  from data.exchange_client import get_exchange, reset_exchange
  reset_exchange()
  ex = get_exchange()
  print('api_public', (ex.urls.get('api') or {}).get('public'))
  bal = ex.fetch_balance()
  usdt = bal.get('USDT') or {}
  print('USDT_free', usdt.get('free'))
  print('USDT_total', usdt.get('total'))
  info = bal.get('info') or {}
  print('uid', info.get('uid'))
except Exception as e:
  print('BINANCE_ERR', type(e).__name__, str(e)[:240])
try:
  from operations.symbol_registry import get_symbol_registry
  r = get_symbol_registry()
  loaded = r.load(s.trading_pairs)
  print('symbols', len(loaded))
except Exception as e:
  print('SYMBOLS_ERR', e)
"""
    remote = KEEP + r"\_health_check.py"
    sftp = ssh.open_sftp()
    try:
        with sftp.file(remote.replace("\\", "/"), "w") as f:
            f.write(diag)
    except Exception as exc:
        print("SFTP_WRITE_FAIL", exc)
    finally:
        sftp.close()

    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"if (Test-Path '{KEEP}\\main.py') {{ Set-Location '{KEEP}'; & '{PY}' _health_check.py }} else {{ 'NO_PACKAGE' }}\"",
        timeout=180,
    )

    # 10) Autologon / power / sleep settings that cause logoff
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"powercfg /query SCHEME_CURRENT SUB_SLEEP 2>$null | Select-String -Pattern 'Current AC|Current DC|Sleep|Hibernate' | Select-Object -First 20; "
        "Write-Output '---'; "
        "Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon' -EA SilentlyContinue | "
        "Select-Object AutoAdminLogon,DefaultUserName | Format-List\"",
    )

    ssh.close()
    print("\nHEALTH_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
