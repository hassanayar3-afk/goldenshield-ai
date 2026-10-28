"""Bootstrap GoldenShield Terminal — مسارات، أسرار، .env."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


def official_root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    path = Path(raw)
    if path.is_dir():
        return path
    return Path.cwd()


def bootstrap() -> None:
    root = official_root()
    try:
        os.chdir(root)
    except Exception:
        pass
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


bootstrap()

ROOT = official_root()
PORT = int(os.getenv("MOBILE_API_PORT", "8790") or 8790)
MASTER_TOKEN = (os.getenv("MOBILE_API_TOKEN") or "").strip() or secrets.token_urlsafe(24)
STRATEGY_CODE = (
    os.getenv("GS_STRATEGY_CODE") or os.getenv("GS_PAIR_CODE") or "GS-GOLD80"
).strip().upper()
_raw_pair = (os.getenv("MOBILE_PAIR_CODE") or "").strip().upper()
if not _raw_pair or _raw_pair == STRATEGY_CODE or _raw_pair in {"GS-GOLD80", "GOLD80"}:
    _raw_pair = "GS-LINK" + secrets.token_hex(3).upper()
PAIR_CODE = _raw_pair
DB = ROOT / "storage" / "db" / "goldenshield.db"
RUNTIME = ROOT / "storage" / "runtime"
DEVICES_FILE = RUNTIME / "mobile_devices.json"
ALERTS_FILE = RUNTIME / "mobile_alerts.json"
RUNTIME.mkdir(parents=True, exist_ok=True)
PANEL_ROOT = ROOT / "control-panel-www"
PANEL_ROOT.mkdir(parents=True, exist_ok=True)

_cred_path = RUNTIME / "mobile_api_credentials.txt"
_prev: dict[str, str] = {}
if _cred_path.exists():
    try:
        for _line in _cred_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in _line:
                _k, _v = _line.split("=", 1)
                _prev[_k.strip()] = _v.strip()
    except Exception:
        _prev = {}
_persisted_pair = (_prev.get("MOBILE_PAIR_CODE") or "").strip().upper()
if _persisted_pair and _persisted_pair != STRATEGY_CODE and _persisted_pair not in {
    "GS-GOLD80",
    "GOLD80",
}:
    PAIR_CODE = _persisted_pair

os.environ["MOBILE_PAIR_CODE"] = PAIR_CODE
os.environ["GS_STRATEGY_CODE"] = STRATEGY_CODE

try:
    _cred_path.write_text(
        (
            f"MOBILE_API_TOKEN={MASTER_TOKEN}\n"
            f"MOBILE_PAIR_CODE={PAIR_CODE}\n"
            f"GS_STRATEGY_CODE={STRATEGY_CODE}\n"
            f"MOBILE_API_PORT={PORT}\n"
            f"BASE=http://0.0.0.0:{PORT}\n"
        ),
        encoding="utf-8",
    )
except Exception:
    pass
