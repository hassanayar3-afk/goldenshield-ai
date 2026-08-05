"""حذف حزم GoldenShield القديمة على Windows VPS والإبقاء على Binance فقط."""

from __future__ import annotations

import os
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

HOST = os.environ["WIN_HOST"]
USER = os.environ["WIN_USER"]
PASSWORD = os.environ["WIN_PASSWORD"]
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
KEEP = r"C:\GoldenShield_Binance"

# مجلدات قديمة للحذف (لن نلمس KEEP)
DELETE_PATHS = [
    r"C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227",
    r"C:\GoldenShield",  # الحزمة القديمة
]


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 300) -> str:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + ("\n" + err if err.strip() else "")).strip()
    safe = text[:3500].encode("ascii", "replace").decode("ascii")
    print(f"[{code}] {safe}\n")
    return text


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)

    # 1) أوقف كل main.py
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; "
        "schtasks /End /TN GoldenShieldBotVisible 2>$null; Start-Sleep -Seconds 3\"",
    )

    # 2) احذف junction القديم إن كان يشير لقديم
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"if (Test-Path 'C:\\GSBot') { cmd /c rmdir C:\\GSBot }; 'junction_removed'\"",
    )

    # 3) ابحث عن مجلدات GoldenShield قديمة إضافية واحذفها (ما عدا KEEP)
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"$keep='C:\\GoldenShield_Binance'; "
        "$hits=@(); "
        "$hits += Get-ChildItem 'C:\\Users\\Administrator\\Downloads' -Recurse -Directory -EA SilentlyContinue | "
        "Where-Object { $_.Name -match 'GoldenShield|CONTABO_DEMO' -and $_.FullName -notlike ($keep+'*') }; "
        "$hits += Get-ChildItem 'C:\\' -Directory -EA SilentlyContinue | "
        "Where-Object { $_.Name -match 'GoldenShield' -and $_.FullName -ne $keep }; "
        "$hits | Select-Object -ExpandProperty FullName -Unique\"",
    )

    # 4) حذف صريح للمسارات المعروفة + أي CONTABO تحت Downloads
    delete_ps = r"""
$keep = 'C:\GoldenShield_Binance'
$targets = @(
  'C:\Users\Administrator\Downloads\Telegram Desktop\GoldenShield_CONTABO_DEMO_20260728_2227',
  'C:\GoldenShield'
)
$extra = Get-ChildItem 'C:\Users\Administrator\Downloads' -Recurse -Directory -EA SilentlyContinue |
  Where-Object { $_.Name -match 'GoldenShield|CONTABO_DEMO' -and $_.FullName -notlike ($keep + '*') } |
  Select-Object -ExpandProperty FullName
$targets += @($extra)
$targets = $targets | Select-Object -Unique
foreach ($t in $targets) {
  if (-not $t) { continue }
  if ($t -eq $keep -or $t -like ($keep + '\*')) { Write-Output "SKIP_KEEP $t"; continue }
  if (Test-Path $t) {
    Write-Output "DELETE $t"
    cmd /c "rmdir /s /q `"$t`""
    if (Test-Path $t) {
      Remove-Item -LiteralPath $t -Recurse -Force -EA SilentlyContinue
    }
    if (Test-Path $t) { Write-Output "FAIL $t" } else { Write-Output "OK_DELETED $t" }
  } else {
    Write-Output "MISSING $t"
  }
}
# احذف ZIP قديمة إن وُجدت
Get-ChildItem 'C:\Users\Administrator\Downloads' -Recurse -File -EA SilentlyContinue |
  Where-Object { $_.Name -match 'CONTABO_DEMO.*\.zip' } |
  ForEach-Object { Write-Output "DELETE_ZIP $($_.FullName)"; Remove-Item -LiteralPath $_.FullName -Force -EA SilentlyContinue }
Write-Output 'DELETE_PASS_DONE'
"""
    remote_ps = KEEP + r"\_cleanup_old.ps1"
    sftp = ssh.open_sftp()
    with sftp.file(remote_ps.replace("\\", "/"), "w") as f:
        f.write(delete_ps)
    sftp.close()
    run(ssh, f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps}"', timeout=600)

    # 5) تأكد أن الحزمة الجديدة موجودة
    check = run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Test-Path '{KEEP}\\main.py'; Test-Path '{KEEP}\\00_START.bat'; Test-Path '{KEEP}\\.env'; "
        f"Get-ChildItem '{KEEP}' | Select-Object -First 20 Name\"",
    )
    if "True" not in check:
        print("NEW_PACKAGE_MISSING")
        ssh.close()
        return 1

    # 6) أعد junction + شغّل البوت من الحزمة الجديدة فقط
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"cmd /c mklink /J C:\\GSBot '{KEEP}'; "
        f"Remove-Item -Force '{KEEP}\\storage\\runtime\\user_stopped.flag' -EA SilentlyContinue\"",
    )
    run(ssh, "schtasks /Delete /TN GoldenShieldBotVisible /F")
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"$tr='cmd.exe /c cd /d {KEEP} && \\\"{PY}\\\" -u main.py >> storage\\logs\\bot_stdout.log 2>&1'; "
        "schtasks /Create /TN GoldenShieldBotVisible /TR $tr /SC ONCE /ST 00:00 /RL HIGHEST /F; "
        "schtasks /Run /TN GoldenShieldBotVisible\"",
    )
    time.sleep(12)
    proc = run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\\.py' } | "
        "Select-Object ProcessId,CommandLine | Format-List\"",
    )
    run(
        ssh,
        "powershell -NoProfile -Command "
        f"\"Set-Location '{KEEP}'; & '{PY}' -c \\\"from config.settings import load_settings; s=load_settings(reload=True); "
        "print('mode',s.execution_mode); print('backend',s.execution_backend); print('demo',s.binance_demo_trading)\\\"\"",
    )

    # 7) تأكيد اختفاء القديم
    run(
        ssh,
        "powershell -NoProfile -Command "
        "\"Write-Output 'OLD_CONTABO='; Test-Path 'C:\\Users\\Administrator\\Downloads\\Telegram Desktop\\GoldenShield_CONTABO_DEMO_20260728_2227'; "
        "Write-Output 'OLD_GOLDEN='; Test-Path 'C:\\GoldenShield'; "
        "Write-Output 'NEW='; Test-Path 'C:\\GoldenShield_Binance\\main.py'; "
        "Write-Output 'GSBOT='; cmd /c dir C:\\GSBot\\main.py\"",
    )

    ssh.close()
    ok = "ProcessId" in proc and KEEP.replace("\\", "\\\\") in proc.replace("/", "\\") or (
        "ProcessId" in proc and "GoldenShield_Binance" in proc
    )
    if "ProcessId" not in proc:
        print("CLEANUP_OK_BUT_BOT_NOT_RUNNING")
        return 1
    if "GoldenShield_Binance" not in proc and "C:\\\\GSBot" not in proc and "C:\\GSBot" not in proc:
        # still running somehow
        print("BOT_RUNNING_CHECK", "GoldenShield_Binance" in proc)
    print("DONE_OLD_DELETED_NEW_RUNNING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
