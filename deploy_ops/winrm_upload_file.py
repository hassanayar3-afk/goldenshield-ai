#!/usr/bin/env python3
"""Upload one file to VPS with MD5 verification."""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sys
from pathlib import Path

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = r"C:\GoldenShield_Binance"


def session() -> winrm.Session:
    load_dotenv(ROOT / ".env", override=True)
    host = (os.getenv("WIN_HOST") or "").strip()
    user = (os.getenv("WIN_USER") or "").strip()
    password = (os.getenv("WIN_PASSWORD") or "").strip()
    if not (host and user and password):
        raise SystemExit("WIN credentials missing")
    return winrm.Session(
        f"http://{host}:5985/wsman",
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=3600,
        operation_timeout_sec=900,
    )


def upload(rel: str) -> None:
    local = ROOT / rel
    if not local.is_file():
        raise SystemExit(f"missing {local}")
    remote = REMOTE_ROOT + "\\" + rel.replace("/", "\\")
    digest = hashlib.md5(local.read_bytes()).hexdigest()
    data = local.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    s = session()
    parent = str(Path(remote).parent)
    s.run_ps(f"New-Item -ItemType Directory -Force -Path '{parent}' | Out-Null")
    rb = remote + ".b64"
    s.run_ps(f"Remove-Item '{rb}' -Force -EA SilentlyContinue")
    # single write via Set-Content on remote decoded in one shot if small enough; else chunks
    chunk = 3500
    for i in range(0, len(b64), chunk):
        part = b64[i : i + chunk].replace("'", "''")
        s.run_ps(
            f"Add-Content -Path '{rb}' -Value '{part}' -Encoding ASCII -NoNewline"
        )
    verify_ps = f"""
$bytes = [Convert]::FromBase64String((Get-Content '{rb}' -Raw -Encoding ASCII))
[IO.File]::WriteAllBytes('{remote}', $bytes)
Remove-Item '{rb}' -Force
$md = (Get-FileHash '{remote}' -Algorithm MD5).Hash.ToLower()
Write-Output $md
"""
    r = s.run_ps(verify_ps)
    remote_md = (r.std_out or b"").decode().strip().splitlines()[-1].lower()
    if remote_md != digest:
        raise SystemExit(f"MD5 mismatch {rel}: local={digest} remote={remote_md}")
    print(f"OK {rel} md5={digest}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="+")
    args = p.parse_args()
    for f in args.files:
        upload(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
