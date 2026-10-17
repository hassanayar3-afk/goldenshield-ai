#!/usr/bin/env python3
"""Push storage/runtime (and optional DB) from laptop → Contabo for live panel."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNTIME_FILES = (
    "storage/runtime/binance_snapshot.json",
    "storage/runtime/heartbeat.json",
    "storage/runtime/balance_mirror.json",
    "storage/runtime/gs_runtime_status.json",
    "storage/runtime/last_cycle_signals.json",
    "storage/runtime/signals_board.txt",
)

OPTIONAL_DB = "storage/db/goldenshield.db"


def _remote_root() -> str:
    raw = (os.getenv("RUNTIME_SYNC_REMOTE_ROOT") or r"C:\GoldenShield_Binance").strip()
    return raw.rstrip("/\\")


def _sftp_remote_path(rel: str) -> str:
    """OpenSSH SFTP on Windows: /C:/GoldenShield_Binance/storage/runtime/file.json"""
    root = _remote_root().replace("\\", "/")
    if len(root) >= 2 and root[1] == ":":
        root = "/" + root
    rel_posix = rel.replace("\\", "/").lstrip("/")
    return f"{root}/{rel_posix}"


def _sftp_put(sftp, local: Path, remote_rel: str) -> bool:
    remote = _sftp_remote_path(remote_rel)
    remote_dir = remote.rsplit("/", 1)[0]
    parts = [p for p in remote_dir.split("/") if p]
    acc = ""
    for p in parts:
        acc = f"{acc}/{p}" if acc else (f"/{p}" if not p.endswith(":") else p)
        if acc.endswith(":"):
            continue
        try:
            sftp.stat(acc)
        except OSError:
            try:
                sftp.mkdir(acc)
            except OSError:
                pass
    try:
        sftp.put(str(local), remote)
        return True
    except OSError:
        return False


def sync_once(*, include_db: bool = False, root: Path | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv(root or ROOT / ".env", override=True)
    load_dotenv(root or ROOT / "goldenshield.env", override=True)

    base = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or root or ROOT)
    try:
        from scripts._win_ssh import connect_windows_ssh
    except ImportError:
        print("paramiko / _win_ssh unavailable", file=sys.stderr)
        return 2

    ssh = connect_windows_ssh(timeout=60)
    try:
        sftp = ssh.open_sftp()
        ok = 0
        missing = 0
        for rel in RUNTIME_FILES:
            local = base / rel
            if not local.is_file():
                missing += 1
                continue
            if _sftp_put(sftp, local, rel):
                ok += 1
        if include_db:
            db_local = base / OPTIONAL_DB
            if db_local.is_file():
                if _sftp_put(sftp, db_local, OPTIONAL_DB):
                    ok += 1
        print(f"SYNC_OK files={ok} missing={missing} remote={_remote_root()}")
        return 0 if ok else 1
    finally:
        ssh.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync runtime JSON to Contabo panel")
    parser.add_argument("--include-db", action="store_true", help="Also upload goldenshield.db")
    parser.add_argument("--root", default="", help="Override project root")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else ROOT
    try:
        return sync_once(include_db=args.include_db, root=root)
    except Exception as exc:
        print(f"SFTP_SYNC_FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        try:
            from scripts.sync_runtime_winrm import sync_once as winrm_sync

            return winrm_sync(include_db=args.include_db, root=root)
        except Exception as exc2:
            print(f"SYNC_FAIL {type(exc2).__name__}: {exc2}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
