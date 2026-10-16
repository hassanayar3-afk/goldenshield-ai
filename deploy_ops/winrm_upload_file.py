#!/usr/bin/env python3
"""Upload one file to Windows VPS with MD5 verification (binary-chunk WinRM)."""

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
    data = local.read_bytes()
    digest = hashlib.md5(data).hexdigest()
    s = session()
    parent = str(Path(remote).parent)
    s.run_ps(f"New-Item -ItemType Directory -Force -Path '{parent}' | Out-Null")
    s.run_ps(f"Remove-Item '{remote}' -Force -EA SilentlyContinue")
    first = True
    for i in range(0, len(data), 1800):
        chunk = base64.b64encode(data[i : i + 1800]).decode("ascii").replace('"', '`"')
        mode = "Create" if first else "Append"
        first = False
        s.run_ps(
            f'$b=[Convert]::FromBase64String("{chunk}"); '
            f'$fs=[IO.File]::Open("{remote}", [IO.FileMode]::{mode}, [IO.FileAccess]::Write); '
            f"$fs.Write($b,0,$b.Length); $fs.Close()"
        )
    r = s.run_ps(
        f"Write-Output ((Get-FileHash '{remote}' -Algorithm MD5).Hash.ToLower())"
    )
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
