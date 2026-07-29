"""نشر مراقب البنية على Contabo + cron كل 5 دقائق."""

from __future__ import annotations

import io
import os
import tarfile
import tempfile
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

EXCLUDE_DIRS = {".venv", "__pycache__", ".git", ".pytest_cache", ".cursor", "htmlcov"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".db", ".zip"}


def build_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if set(rel.parts) & EXCLUDE_DIRS:
                continue
            if rel.suffix in EXCLUDE_SUFFIX:
                continue
            if rel.name == ".env":
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
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 300) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace") + stderr.read().decode(
        "utf-8", errors="replace"
    )


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        print("TELEGRAM_CHAT_ID مطلوب")
        return 1

    archive = build_archive()
    client = ssh_connect()
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/goldenshield_watchdog.tar.gz", "wb") as remote:
            remote.write(archive)
        sftp.close()

        script = f"""
set -euo pipefail
cd /opt/goldenshield
tar -xzf /tmp/goldenshield_watchdog.tar.gz -C /opt/goldenshield
chmod +x deployment/run_infrastructure_watchdog.sh
mkdir -p storage/logs

for kv in \\
  'WATCHDOG_ENABLED=true' \\
  'WATCHDOG_CHAT_ID={chat_id}' \\
  'WATCHDOG_WINDOWS_HOST=169.58.15.36' \\
  'WATCHDOG_WINDOWS_PORT=3389' \\
  'WATCHDOG_CONTAINER=goldenshield-bot' \\
  'WATCHDOG_STALE_MINUTES=15' \\
  'WATCHDOG_REMIND_HOURS=6' \\
  'WATCHDOG_CHECK_WINDOWS=true'
do
  key="${{kv%%=*}}"
  val="${{kv#*=}}"
  if grep -q "^$key=" .env; then
    sed -i "s/^$key=.*/$key=$val/" .env
  else
    echo "$key=$val" >> .env
  fi
done

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
CRON_LINE='*/5 * * * * /opt/goldenshield/deployment/run_infrastructure_watchdog.sh'
( crontab -l 2>/dev/null | grep -v 'run_infrastructure_watchdog' ; echo "$CRON_LINE" ) | crontab -
echo '--- cron ---'
crontab -l | grep watchdog || true
echo '--- run now ---'
bash deployment/run_infrastructure_watchdog.sh || true
tail -n 25 storage/logs/watchdog.log || true
"""
        print(run(client, script, timeout=600))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
