"""مزامنة الكود + الإعدادات على Contabo ثم إرسال حزمة Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.deploy_to_contabo import build_archive, production_env  # noqa: E402


def sync_contabo() -> int:
    from scripts._deploy_env import require_deploy_credentials

    host, user, password = require_deploy_credentials()

    print("Building archive...")
    archive = build_archive()
    print(f"Archive size: {len(archive) / 1024:.1f} KB")

    env_text = production_env()
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
    try:
        sftp = client.open_sftp()
        remote_tar = "/tmp/goldenshield_sync.tar.gz"
        with sftp.file(remote_tar, "wb") as rf:
            rf.write(archive)
        with sftp.file("/opt/goldenshield/.env", "w") as ef:
            ef.write(env_text)
        sftp.chmod("/opt/goldenshield/.env", 0o600)
        sftp.close()
        print("Code + .env uploaded (auto ≥90)")

        cmd = f"""
set -e
tar -xzf {remote_tar} -C /opt/goldenshield
rm -f {remote_tar}
cd /opt/goldenshield
docker compose up -d --build --force-recreate
sleep 8
docker inspect -f '{{{{.State.Status}}}}' goldenshield-bot
grep -E 'AUTO_ENTRY|MANUAL_ENTRY|BUILD_TAG' .env /opt/goldenshield/main.py 2>/dev/null | head -5
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=1200)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        print(out[-4000:].encode("ascii", "replace").decode("ascii"))
        if err.strip():
            print(err[-1500:].encode("ascii", "replace").decode("ascii"))
        return 0 if "running" in out else 2
    finally:
        client.close()


def send_windows_zip() -> int:
    from scripts.send_simple_windows_zip import main as send_zip

    return int(send_zip())


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    print("=== 1) Contabo code + settings ===")
    code = sync_contabo()
    if code != 0:
        print("Contabo sync failed:", code)
    print("=== 2) Windows ZIP to Telegram ===")
    zip_code = send_windows_zip()
    return zip_code if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
