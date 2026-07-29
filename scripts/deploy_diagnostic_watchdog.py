"""رفع مراقب التشخيص وتشغيل فحص + إرسال تنبيه تشخيصي."""

from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._deploy_env import require_deploy_credentials  # noqa: E402

FILES = [
    "operations/infrastructure_watchdog.py",
    "operations/message_templates.py",
    "deployment/run_infrastructure_watchdog.sh",
]


def main() -> int:
    host, user, password = require_deploy_credentials()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in FILES:
            path = ROOT / rel
            tar.add(path, arcname=rel)
    data = buf.getvalue()

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
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/wd_diag.tar.gz", "wb") as fh:
            fh.write(data)
        sftp.close()

        cmd = r"""
set -e
cd /opt/goldenshield
tar -xzf /tmp/wd_diag.tar.gz
chmod +x deployment/run_infrastructure_watchdog.sh
# فرض تنبيه تشخيصي جديد (مسح الحالة)
rm -f storage/logs/infrastructure_watchdog_state.json
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
# تأكد cron
CRON_LINE='*/5 * * * * /opt/goldenshield/deployment/run_infrastructure_watchdog.sh'
( crontab -l 2>/dev/null | grep -v run_infrastructure_watchdog ; echo "$CRON_LINE" ) | crontab -
bash deployment/run_infrastructure_watchdog.sh || true
echo '---LOG---'
tail -20 storage/logs/watchdog.log
echo '---CRON---'
crontab -l | grep watchdog
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=300)
        print(stdout.read().decode("utf-8", "replace")[-6000:])
        err = stderr.read().decode("utf-8", "replace")
        if err:
            print(err[-1500:])
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
