"""Project root bootstrap: path, cwd, .env at workspace root."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def setup_sovereign_root() -> Path:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return ROOT


def load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv

        env_path = ROOT / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=False)
    except Exception:
        pass
