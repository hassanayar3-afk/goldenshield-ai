#!/usr/bin/env python3
"""Push storage/runtime files to Contabo via WinRM (when SSH/SFTP unavailable)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sync_runtime_to_contabo import RUNTIME_FILES, OPTIONAL_DB  # noqa: E402


def sync_once(*, include_db: bool = False, root: Path | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv(root or ROOT / ".env", override=True)
    load_dotenv(root or ROOT / "goldenshield.env", override=True)

    from scripts.remote_vps_apply_winrm import REMOTE, _session, _upload_bytes

    base = Path(__import__("os").getenv("GOLDENSHIELD_OFFICIAL_ROOT") or root or ROOT)
    session = _session()
    ok = 0
    for rel in RUNTIME_FILES:
        local = base / rel
        if not local.is_file():
            continue
        remote = REMOTE + "\\" + rel.replace("/", "\\")
        _upload_bytes(session, remote, local.read_bytes())
        ok += 1
    if include_db:
        db = base / OPTIONAL_DB
        if db.is_file():
            _upload_bytes(session, REMOTE + "\\" + OPTIONAL_DB.replace("/", "\\"), db.read_bytes())
            ok += 1
    print(f"WINRM_SYNC_OK files={ok} remote={REMOTE}")
    return 0 if ok else 1


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--include-db", action="store_true")
    p.add_argument("--root", default="")
    args = p.parse_args()
    root = Path(args.root).resolve() if args.root else ROOT
    try:
        return sync_once(include_db=args.include_db, root=root)
    except Exception as exc:
        print(f"WINRM_SYNC_FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
