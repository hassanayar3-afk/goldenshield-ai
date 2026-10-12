"""نشر GoldenShield مباشرة إلى Windows VPS + فحص."""

from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env", override=True)

from scripts._win_ssh import (  # noqa: E402
    WindowsSSHError,
    connect_windows_ssh,
    load_local_env_for_deploy,
)

REMOTE_DIR = r"C:\GoldenShield_Binance"

EXCLUDE_DIRS = {".venv", "__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".cursor", "htmlcov", "tests", ".github", "docs", "saas"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDE_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    ".dockerignore",
    "SESSION_STATE.md",
    "pytest.ini",
}


def should_skip(rel: Path) -> bool:
    if set(rel.parts) & EXCLUDE_DIRS:
        return True
    if rel.suffix in EXCLUDE_SUFFIXES:
        return True
    if rel.name == ".env":
        return True
    if rel.name in EXCLUDE_FILES:
        return True
    return False


def build_archive() -> bytes:
    from scripts.windows_package import CHECK_BAT, START_BAT, STOP_BAT, production_env

    local = load_local_env_for_deploy()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if should_skip(rel):
                continue
            tar.add(path, arcname=str(rel).replace("\\", "/"))

        def add_text(name: str, content: str) -> None:
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        add_text(".env", production_env(local))
        add_text("00_START.bat", START_BAT)
        add_text("00_STOP.bat", STOP_BAT)
        add_text("فحص_المجلد_CHECK.bat", CHECK_BAT)
    return buf.getvalue()


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print("$", cmd)
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-4000:])
    if err.strip():
        print(err[-2000:])
    return code, out + err


def main() -> int:
    try:
        archive = build_archive()
    except OSError as exc:
        print(f"build_archive failed: {exc}")
        return 1
    print(f"archive={len(archive)/1024:.1f} KB")

    try:
        ssh = connect_windows_ssh(timeout=45)
    except WindowsSSHError as exc:
        print(exc, file=sys.stderr)
        return 3

    run(
        ssh,
        rf'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path {REMOTE_DIR}, {REMOTE_DIR}\storage\db\backups, {REMOTE_DIR}\storage\logs, {REMOTE_DIR}\storage\runtime | Out-Null"',
    )

    sftp = ssh.open_sftp()
    remote_tar_win = rf"{REMOTE_DIR}\_deploy.tgz"
    with sftp.file(remote_tar_win.replace("\\", "/"), "wb") as rf:
        rf.write(archive)
    sftp.close()

    code, _ = run(
        ssh,
        rf'powershell -NoProfile -Command "Set-Location {REMOTE_DIR}; tar -xzf _deploy.tgz; Remove-Item _deploy.tgz -Force -ErrorAction SilentlyContinue"',
        timeout=300,
    )
    if code != 0:
        ssh.close()
        return 1

    run(ssh, rf'powershell -NoProfile -Command "Get-ChildItem {REMOTE_DIR} | Select-Object Name,Length | Format-Table -AutoSize"')
    run(ssh, rf'powershell -NoProfile -Command "Test-Path {REMOTE_DIR}\requirements.txt; Test-Path {REMOTE_DIR}\main.py; Test-Path {REMOTE_DIR}\00_START.bat"')
    run(ssh, rf'powershell -NoProfile -Command "Set-Location {REMOTE_DIR}; py -m pip install -r requirements.txt"', timeout=900)
    run(ssh, rf'powershell -NoProfile -Command "Set-Location {REMOTE_DIR}; py scripts\bootstrap_storage.py"', timeout=120)

    run(
        ssh,
        rf'powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-Location {REMOTE_DIR}; '
        rf'if (Test-Path deploy\windows\INSTALL_GOLDENSHIELD_TERMINAL.ps1) {{ '
        rf'Set-ExecutionPolicy -Scope Process Bypass; .\deploy\windows\INSTALL_GOLDENSHIELD_TERMINAL.ps1 }} "',
        timeout=900,
    )
    run(
        ssh,
        rf'powershell -NoProfile -ExecutionPolicy Bypass -File {REMOTE_DIR}\deploy\windows\GS_START_FULL_STACK.ps1 -Root {REMOTE_DIR}',
        timeout=180,
    )
    code_health, out_health = run(
        ssh,
        rf'powershell -NoProfile -Command "try {{ (Invoke-RestMethod -Uri http://127.0.0.1:8790/api/health -TimeoutSec 15).ok }} catch {{ $_.Exception.Message }}"',
        timeout=60,
    )
    print("REMOTE_HEALTH", out_health.strip()[:200])

    ssh.close()
    print("WINDOWS_DEPLOY_DONE C:\\GoldenShield_Binance")
    return 0 if code_health == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
