"""نشر GoldenShield إلى Contabo عبر SSH/SFTP — لا ترفع كلمات المرور إلى Git."""

from __future__ import annotations

import io
import os
import tarfile
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE_DIR = "/opt/goldenshield"

EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".cursor",
    "htmlcov",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    if path.name == ".env":
        return True  # نكتب .env إنتاج على السيرفر منفصلاً
    return False


def build_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if _should_skip(rel):
                continue
            tar.add(path, arcname=str(rel).replace("\\", "/"))
    return buf.getvalue()


def ssh_connect() -> paramiko.SSHClient:
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts._deploy_env import require_deploy_credentials

    host, user, password = require_deploy_credentials()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        username=user,
        password=password,
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-4000:].encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print(err[-2000:].encode("ascii", "replace").decode("ascii"))
    return code, out, err


def production_env() -> str:
    # اقرأ القيم المحلية دون طباعتها
    local = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            local[k.strip()] = v.strip()

    values = {
        "ENV": "production",
        # live + demo = حساب الديمو (أموال وهمية) — ليس الحساب الحقيقي
        "EXECUTION_MODE": "live",
        "EXECUTION_BACKEND": "binance",
        "BINANCE_DEMO_TRADING": "true",
        "MT5_ENABLED": "false",
        "MANUAL_ENTRY_REQUIRED": "false",
        "AUTO_ENTRY_MIN_PERCENT": "95",
        "MAX_CONCURRENT_POSITIONS": "12",
        "HIGH_CONVICTION_MODE": "false",
        "STANDARD_BONUS_PROFILE": "false",
        "TRIAL_MODE": "false",
        "TRIAL_JOURNAL_ENABLED": "true",
        "BOT_ADMIN_FULL_ACCESS": "true",
        "BOT_AUTO_SYNC_MT5": "false",
        "TELEGRAM_TOKEN": local.get("TELEGRAM_TOKEN", ""),
        "TELEGRAM_BOT_USERNAME": local.get("TELEGRAM_BOT_USERNAME", "GoldenShield_2026_bot"),
        "TELEGRAM_CHAT_ID": local.get("TELEGRAM_CHAT_ID", ""),
        "TELEGRAM_BACKUP_CHANNEL_ID": local.get("TELEGRAM_BACKUP_CHANNEL_ID", "-1004462420308"),
        "TELEGRAM_SEND_CYCLE_SIGNALS": "false",
        "TELEGRAM_SIGNALS_ONLY": "true",
        "LOOP_INTERVAL_SECONDS": "15",
        "DB_PATH": "storage/db/goldenshield.db",
        "BINANCE_API_KEY": local.get("BINANCE_API_KEY", ""),
        "BINANCE_API_SECRET": local.get("BINANCE_API_SECRET", ""),
        "BINANCE_API_KEY_2": local.get("BINANCE_API_KEY_2", ""),
        "BINANCE_API_SECRET_2": local.get("BINANCE_API_SECRET_2", ""),
        "WATCHDOG_ENABLED": "true",
        "WATCHDOG_CHAT_ID": local.get("WATCHDOG_CHAT_ID") or local.get("TELEGRAM_CHAT_ID", ""),
        "WATCHDOG_WINDOWS_HOST": local.get("WATCHDOG_WINDOWS_HOST", "169.58.15.36"),
        "WATCHDOG_WINDOWS_PORT": local.get("WATCHDOG_WINDOWS_PORT", "3389"),
        "WATCHDOG_CONTAINER": "goldenshield-bot",
        "WATCHDOG_STALE_MINUTES": "15",
        "WATCHDOG_REMIND_HOURS": "6",
        "WATCHDOG_CHECK_WINDOWS": "true",
    }
    lines = [f"{k}={v}" for k, v in values.items()]
    return "\n".join(lines) + "\n"


def main() -> int:
    print("Building archive...")
    archive = build_archive()
    print(f"Archive size: {len(archive) / 1024:.1f} KB")

    client = ssh_connect()
    try:
        # أساسيات النظام + Docker
        setup = r"""
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 git curl ca-certificates
systemctl enable --now docker
mkdir -p /opt/goldenshield/storage/db/backups /opt/goldenshield/storage/logs
docker --version
docker compose version
"""
        code, _, _ = run(client, setup, timeout=900)
        if code != 0:
            print("Setup failed", code)
            return 1

        # رفع الأرشيف
        sftp = client.open_sftp()
        remote_tar = "/tmp/goldenshield_deploy.tar.gz"
        print("Uploading archive...")
        with sftp.file(remote_tar, "wb") as rf:
            rf.write(archive)

        # استخراج بدون مسح storage إن وُجد لاحقاً — أول نشر كامل
        extract = f"""
set -e
mkdir -p {REMOTE_DIR}
tar -xzf {remote_tar} -C {REMOTE_DIR}
rm -f {remote_tar}
mkdir -p {REMOTE_DIR}/storage/db/backups {REMOTE_DIR}/storage/logs
"""
        code, _, _ = run(client, extract)
        if code != 0:
            return 1

        # كتابة .env إنتاج
        env_text = production_env()
        with sftp.file(f"{REMOTE_DIR}/.env", "w") as ef:
            ef.write(env_text)
        sftp.chmod(f"{REMOTE_DIR}/.env", 0o600)
        sftp.close()
        print(".env written on server")

        # systemd + تشغيل
        unit = f"""
set -e
cp {REMOTE_DIR}/deployment/systemd/goldenshield.service /etc/systemd/system/goldenshield.service
systemctl daemon-reload
systemctl enable goldenshield
cd {REMOTE_DIR}
docker compose down || true
docker compose up -d --build
sleep 8
docker compose ps
docker logs --tail 40 goldenshield-bot || true
"""
        code, out, err = run(client, unit, timeout=1200)
        if code != 0:
            print("Compose failed", code)
            return 1

        # فحص سريع أن الحاوية تعمل
        code2, out2, _ = run(client, "docker inspect -f '{{.State.Status}}' goldenshield-bot")
        status = out2.strip().strip("'")
        print("CONTAINER_STATUS=", status)
        return 0 if status == "running" else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
