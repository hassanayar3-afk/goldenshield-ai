"""فحص سريع لاتصال Contabo عبر SSH — يعتمد على .env."""

from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts._deploy_env import require_deploy_credentials  # noqa: E402

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

cmds = [
    'docker ps --filter name=goldenshield-bot --format "{{.Names}} | {{.Status}}"',
    "systemctl is-enabled goldenshield; systemctl is-active goldenshield || true",
    "docker logs --tail 30 goldenshield-bot 2>&1",
]
for cmd in cmds:
    print("===", cmd)
    _, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out or err)

client.close()
