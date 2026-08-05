"""ضبط .env التشغيلي دون لمس الأسرار الموجودة."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

# قيم تشغيل مؤسسية — لا تتضمن أسراراً
PATCHES: dict[str, str] = {
    "ENV": "dev",
    "EXECUTION_MODE": "paper",
    "EXECUTION_BACKEND": "binance",
    "AUTO_ENTRY_MIN_PERCENT": "95",
    "MANUAL_ENTRY_REQUIRED": "false",
    "IRON_PROTOCOL_ENABLED": "true",
    "PRE_EXECUTION_GATE_ENABLED": "true",
    "EMERGENCY_PROTOCOLS_ENABLED": "true",
    "EMERGENCY_ATR_SL_ENABLED": "true",
    "RISK_DISTANCE_FILTER_ENABLED": "true",
    "SL_RR_LOCK_ENABLED": "true",
    "SL_RR_LOCK_RATIO": "3.0",
    "VOLATILITY_GUARD_ENABLED": "true",
    "REQUIRE_SL_ON_ALL_CHUNKS": "true",
    "CLOSE_NAKED_TICKETS": "true",
    "MANAGE_POSITIONS_DURING_HALT": "true",
    "TELEGRAM_SIGNALS_ONLY": "true",
    "TELEGRAM_SEND_CYCLE_SIGNALS": "false",
    "LOOP_INTERVAL_SECONDS": "15",
    "HIGH_CONVICTION_MODE": "false",
    "STANDARD_BONUS_PROFILE": "false",
    "TRIAL_MODE": "false",
    "MAX_CONCURRENT_POSITIONS": "12",
    "BINANCE_DEMO_TRADING": "true",
}

PLACEHOLDER_KEYS = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_API_KEY_2",
    "BINANCE_API_SECRET_2",
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def main() -> None:
    if not ENV_PATH.exists():
        example = ROOT / ".env.example"
        ENV_PATH.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print("created .env from .env.example")

    lines = ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    existing: dict[str, str] = {}
    order: list[str] = []
    for line in lines:
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            order.append(line)
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        existing[key] = val
        order.append(f"__KEY__{key}")

    for key, val in PATCHES.items():
        existing[key] = val

    for key in PLACEHOLDER_KEYS:
        if key not in existing:
            existing[key] = ""

    out: list[str] = []
    seen: set[str] = set()
    for item in order:
        if item.startswith("__KEY__"):
            key = item[len("__KEY__") :]
            out.append(f"{key}={existing.get(key, '')}")
            seen.add(key)
        else:
            out.append(item)

    for key, val in existing.items():
        if key not in seen:
            out.append(f"{key}={val}")
            seen.add(key)

    # تذييل توضيحي مرة واحدة
    marker = "# —— GoldenShield v1.3 operational defaults applied ——"
    if marker not in "\n".join(out):
        out.append("")
        out.append(marker)
        out.append("# Secrets (Binance/Telegram) left as-is; fill missing when ready.")

    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("patched .env operational defaults (secrets preserved)")


if __name__ == "__main__":
    main()
