"""تشغيل Windows التلقائي — قاعدة البيانات + MT5 + بوت الإشارات."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)

DEFAULT_MT5_PATHS = (
    Path(r"C:\Program Files\MetaTrader 5\terminal64.exe"),
    Path(r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"),
)


def wait_for_network(*, timeout_seconds: int = 180, interval_seconds: int = 10) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "8.8.8.8"],
                capture_output=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
        time.sleep(interval_seconds)
    return False


def resolve_mt5_terminal() -> Path | None:
    custom = os.getenv("MT5_TERMINAL_PATH", "").strip()
    if custom:
        path = Path(custom)
        if path.exists():
            return path
    for candidate in DEFAULT_MT5_PATHS:
        if candidate.exists():
            return candidate
    return None


def is_mt5_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return "terminal64.exe" in (result.stdout or "").lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


def start_mt5_terminal() -> bool:
    if is_mt5_running():
        logger.info("MT5 already running")
        return True
    terminal = resolve_mt5_terminal()
    if terminal is None:
        logger.warning("MT5 terminal not found — افتحه يدوياً أو عيّن MT5_TERMINAL_PATH")
        return False
    try:
        subprocess.Popen(
            [str(terminal)],
            cwd=str(terminal.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("MT5 started: %s", terminal)
        time.sleep(20)
        return True
    except OSError:
        logger.exception("فشل تشغيل MT5")
        return False


def prepare_boot_environment() -> int:
    os.chdir(ROOT)
    if os.getenv("GOLDENSHIELD_BOOT", "").strip().lower() in {"1", "true", "yes", "on"}:
        from operations.shutdown_guard import clear_user_stop

        clear_user_stop()

    from scripts.bootstrap_storage import bootstrap

    db_path = bootstrap(reload_settings=True)
    print(f"boot:database={db_path}")

    if not wait_for_network():
        print("boot:network_timeout", file=sys.stderr)
        return 2

    print("boot:network_ok")
    start_mt5_terminal()
    return 0


def launch_signal_supervisor() -> int:
    start_bat = ROOT / "00_START.bat"
    if not start_bat.exists():
        start_bat = ROOT / "scripts" / "00_START_AUTO.bat"
    if not start_bat.exists():
        print("boot:missing_start_bat", file=sys.stderr)
        return 1
    subprocess.Popen(
        ["cmd.exe", "/c", str(start_bat)],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print(f"boot:supervisor_started:{start_bat.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = argv if argv is not None else sys.argv[1:]
    cmd = (args[0] if args else "full").lower()

    if cmd == "prepare":
        return prepare_boot_environment()
    if cmd == "supervisor":
        return launch_signal_supervisor()
    code = prepare_boot_environment()
    if code != 0:
        return code
    return launch_signal_supervisor()


if __name__ == "__main__":
    raise SystemExit(main())
