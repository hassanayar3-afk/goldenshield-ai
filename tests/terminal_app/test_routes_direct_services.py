"""Routes must not import mobile_core facade."""

from __future__ import annotations

from pathlib import Path


def test_routes_use_service_modules_not_mobile_core():
    routes_dir = Path(__file__).resolve().parents[2] / "terminal_app" / "routes"
    offenders = []
    for path in routes_dir.glob("*.py"):
        if path.name == "mobile_core.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "mobile_core" in text:
            offenders.append(path.name)
    assert offenders == [], f"routes still use mobile_core: {offenders}"
