"""نشر ملفات التشغيل المنظمة + آخر تحسينات المشروع إلى VPS."""

from __future__ import annotations

import os
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
    "START_BOT.bat",
    "STOP_BOT.bat",
    "REST_BOT.bat",
    "run_official_bot.bat",
    "00_START.bat",
    "00_STOP.bat",
    "00_LIVE_CONSOLE.bat",
    "LAUNCHERS_AR.txt",
    "main.py",
    "execution/smart_exits.py",
    "execution/trade_executor.py",
    "execution/position_manager.py",
    "operations/telegram_dashboard.py",
    "operations/telegram_commands.py",
    "operations/telegram_keyboards.py",
    "operations/dashboard_templates.py",
    "operations/report_archive.py",
    "operations/trial_journal.py",
    "operations/error_logger.py",
    "config/settings.py",
    "config/risk_params.yaml",
    "database/repositories/trade_repo.py",
    "database/repositories/operations_repo.py",
    "core/technical/signal_scorer.py",
    "core/constants.py",
]

PS = r"""
$ErrorActionPreference='Continue'
$g='C:\GoldenShield_Binance'
Write-Host '=== INSTALL_LAUNCHERS ==='

# اختصارات سطح المكتب بأسماء عربية/واضحة
$desk=[Environment]::GetFolderPath('Desktop')
$targets=@(
  @{Name='START BOT.lnk'; Target=(Join-Path $g 'START_BOT.bat')},
  @{Name='STOP BOT.lnk'; Target=(Join-Path $g 'STOP_BOT.bat')},
  @{Name='REST BOT.lnk'; Target=(Join-Path $g 'REST_BOT.bat')}
)
$w=New-Object -ComObject WScript.Shell
foreach($t in $targets){
  $lnk=Join-Path $desk $t.Name
  $s=$w.CreateShortcut($lnk)
  $s.TargetPath=$t.Target
  $s.WorkingDirectory=$g
  $s.Save()
  Write-Host ('SHORTCUT ' + $t.Name)
}

# مهمة رسمية
$launcher=Join-Path $g 'run_official_bot.bat'
schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null
schtasks /Create /TN GoldenShieldBotOfficial /TR $launcher /SC ONSTART /RL HIGHEST /F | Out-Null
Write-Host 'TASK_OK'

# تشغيل عبر START المنظم
& (Join-Path $g 'START_BOT.bat')
Start-Sleep 10
$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count
Write-Host ('MAIN=' + $n)
Write-Host ('HAS_START=' + (Test-Path (Join-Path $g 'START_BOT.bat')))
Write-Host ('HAS_STOP=' + (Test-Path (Join-Path $g 'STOP_BOT.bat')))
Write-Host ('HAS_REST=' + (Test-Path (Join-Path $g 'REST_BOT.bat')))
if($n -ge 1){ Write-Host 'LAUNCHERS_OK' } else { Write-Host 'LAUNCHERS_CHECK' }
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)
    try:
        def run(cmd: str, timeout: int = 300) -> str:
            _, o, e = ssh.exec_command(cmd, timeout=timeout)
            return (o.read() + e.read()).decode("utf-8", errors="replace")

        sftp = ssh.open_sftp()
        for rel in UPLOADS:
            local = ROOT / rel
            if not local.is_file():
                print("SKIP", rel)
                continue
            remote = f"{KEEP}\\{rel.replace('/', '\\')}"
            remote_dir = str(Path(remote).parent).replace("/", "\\")
            run(
                "powershell -NoProfile -Command "
                f"\"New-Item -ItemType Directory -Force -Path '{remote_dir}' | Out-Null\""
            )
            sftp.put(str(local), remote)
            print("UPLOADED", rel)

        remote_ps = r"C:\ProgramData\GoldenShield\install_launchers.ps1"
        with sftp.file(remote_ps, "w") as fh:
            fh.write(PS.replace("\r\n", "\n").replace("\n", "\r\n"))
        sftp.close()

        # START_BOT.bat has timeout/pause that may hang if run via & — run core pieces instead
        out = run(
            r'powershell -NoProfile -ExecutionPolicy Bypass -Command "'
            r"$g='C:\GoldenShield_Binance'; "
            r"$desk=[Environment]::GetFolderPath('Desktop'); "
            r"$w=New-Object -ComObject WScript.Shell; "
            r"foreach($n in @('START BOT','STOP BOT','REST BOT')){ "
            r"  $bat=Join-Path $g ($n.Replace(' ','_')+'.bat'); "
            r"  if($n -eq 'START BOT'){ $bat=Join-Path $g 'START_BOT.bat' } "
            r"  elseif($n -eq 'STOP BOT'){ $bat=Join-Path $g 'STOP_BOT.bat' } "
            r"  else { $bat=Join-Path $g 'REST_BOT.bat' }; "
            r"  $s=$w.CreateShortcut((Join-Path $desk ($n+'.lnk'))); $s.TargetPath=$bat; $s.WorkingDirectory=$g; $s.Save(); "
            r"  Write-Host ('SHORTCUT '+$n) "
            r"}; "
            r"$launcher=Join-Path $g 'run_official_bot.bat'; "
            r"schtasks /Delete /TN GoldenShieldBotOfficial /F 2>$null | Out-Null; "
            r"schtasks /Create /TN GoldenShieldBotOfficial /TR $launcher /SC ONSTART /RL HIGHEST /F | Out-Null; "
            r"Remove-Item (Join-Path $g 'storage\runtime\user_stopped.flag') -Force -EA SilentlyContinue; "
            r"Remove-Item (Join-Path $g 'storage\runtime\bot_instance.lock') -Force -EA SilentlyContinue; "
            r"Remove-Item 'C:\ProgramData\GoldenShield\bot_instance.lock' -Force -EA SilentlyContinue; "
            r"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }; "
            r"Start-Sleep 2; schtasks /Run /TN GoldenShieldBotOfficial | Out-Null; Start-Sleep 14; "
            r"$n=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'main\.py' }).Count; "
            r"Write-Host ('MAIN='+$n); "
            r"Write-Host ('HAS_START='+(Test-Path (Join-Path $g 'START_BOT.bat'))); "
            r"Write-Host ('HAS_STOP='+(Test-Path (Join-Path $g 'STOP_BOT.bat'))); "
            r"Write-Host ('HAS_REST='+(Test-Path (Join-Path $g 'REST_BOT.bat'))); "
            r"if($n -ge 1){ Write-Host 'LAUNCHERS_OK' } else { Write-Host 'LAUNCHERS_CHECK' }"
            r'"',
            240,
        )
        print(out.encode("ascii", errors="replace").decode("ascii"))
        return 0 if "LAUNCHERS_OK" in out else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
