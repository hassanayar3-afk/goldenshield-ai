#!/usr/bin/env python3
"""P1 — بناء حزمة نشر ZIP للسيرفر (بدون SSH): فك يدوي على Windows VPS."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".cursor",
    "htmlcov",
    "node_modules",
    "dist",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDE_REL_PREFIXES = (
    "storage/db/",
    "storage/runtime/mobile_api_credentials.txt",
)
SKIP_FILES = {".env"}


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except Exception:
        return "unknown"


def _should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    rel_str = str(rel).replace("\\", "/")
    if rel.name in SKIP_FILES:
        return False
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    for prefix in EXCLUDE_REL_PREFIXES:
        if rel_str.startswith(prefix):
            return False
    if rel_str.endswith(".db"):
        return False
    return True


def _env_template() -> str:
    prod = ROOT / "config" / "env.production.template"
    if prod.is_file():
        return prod.read_text(encoding="utf-8")
    example = ROOT / ".env.example"
    return example.read_text(encoding="utf-8") if example.is_file() else ""


def build_zip(output: Path | None = None) -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    sha = _git_sha()
    zip_path = output or (DIST / f"GoldenShield-Terminal-P1-{stamp}-{sha}.zip")
    if zip_path.exists():
        zip_path.unlink()

    manifest = (
        f"GoldenShield Terminal Deployment Package\n"
        f"built_utc={datetime.now(timezone.utc).isoformat()}\n"
        f"git={sha}\n"
        f"target_windows=C:\\GoldenShield_Binance\n"
        f"install_script=deploy/windows/INSTALL_GOLDENSHIELD_TERMINAL.ps1\n"
    )

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if not path.is_file() or not _should_include(path):
                continue
            rel = path.relative_to(ROOT)
            archive.write(path, str(rel).replace("\\", "/"))
            file_count += 1
        archive.writestr(".env.template", _env_template())
        archive.writestr("DEPLOY_MANIFEST.txt", manifest)
        readme = (ROOT / "deploy/windows/QUICKSTART_P1_AR.txt")
        if readme.is_file():
            archive.write(readme, "deploy/windows/QUICKSTART_P1_AR.txt")

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sidecar = zip_path.with_suffix(".zip.sha256")
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii")
    print(f"PACKAGE_OK path={zip_path} files={file_count} sha256={digest}")
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GoldenShield Terminal ZIP for manual VPS deploy")
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()
    try:
        build_zip(args.output)
        return 0
    except Exception as exc:
        print(f"PACKAGE_FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
