"""نشر GoldenShield مباشرة إلى Windows VPS + فحص."""

from __future__ import annotations

import io
import os
import sys
import tarfile
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env", override=True)

HOST = os.environ.get("WIN_HOST", "169.58.15.36")
USER = os.environ.get("WIN_USER", "Administrator")
PASSWORD = os.environ.get("WIN_PASSWORD", "")
REMOTE_DIR = r"C:\GoldenShield"

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

    local: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        local[k.strip()] = v.strip()

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
    if not PASSWORD:
        print("Set WIN_PASSWORD")
        return 1

    archive = build_archive()
    print(f"archive={len(archive)/1024:.1f} KB")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=45, allow_agent=False, look_for_keys=False)

    run(
        ssh,
        r'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path C:\GoldenShield, C:\GoldenShield\storage\db\backups, C:\GoldenShield\storage\logs, C:\GoldenShield\storage\runtime | Out-Null"',
    )

    sftp = ssh.open_sftp()
    remote_tar_win = r"C:\GoldenShield\_deploy.tgz"
    with sftp.file(remote_tar_win.replace("\\", "/"), "wb") as rf:
        rf.write(archive)
    sftp.close()

    code, _ = run(
        ssh,
        r'powershell -NoProfile -Command "Set-Location C:\GoldenShield; tar -xzf _deploy.tgz; Remove-Item _deploy.tgz -Force -ErrorAction SilentlyContinue"',
        timeout=300,
    )
    if code != 0:
        ssh.close()
        return 1

    run(ssh, r'powershell -NoProfile -Command "Get-ChildItem C:\GoldenShield | Select-Object Name,Length | Format-Table -AutoSize"')
    run(ssh, r'powershell -NoProfile -Command "Test-Path C:\GoldenShield\requirements.txt; Test-Path C:\GoldenShield\main.py; Test-Path C:\GoldenShield\00_START.bat"')
    run(ssh, r'powershell -NoProfile -Command "Set-Location C:\GoldenShield; py -m pip install -r requirements.txt MetaTrader5"', timeout=900)
    run(ssh, r'powershell -NoProfile -Command "Set-Location C:\GoldenShield; py scripts\bootstrap_storage.py"', timeout=120)

    ssh.close()
    print("WINDOWS_DEPLOY_DONE C:\\GoldenShield")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
