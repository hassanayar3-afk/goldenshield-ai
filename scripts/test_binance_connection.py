"""اختبار اتصال Binance API (يدعم Demo Trading)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
load_dotenv(BASE / ".env")

KEY = os.getenv("BINANCE_API_KEY", "").strip()
SECRET = os.getenv("BINANCE_API_SECRET", "").strip()
MODE = os.getenv("EXECUTION_MODE", "paper").strip().lower()
DEMO = os.getenv("BINANCE_DEMO_TRADING", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def main() -> int:
    print(f"وضع التنفيذ: {MODE}")
    print(f"Binance Demo Trading: {DEMO}")

    try:
        from data.connection_utils import ping_exchange

        ping_exchange()
        print("✅ Ping عام لـ Binance — ناجح")
    except Exception as exc:
        print(f"❌ Ping عام فشل: {exc}")
        # في مواقع محظورة جغرافياً قد يفشل الـ ping العام؛ نكمل فحص المفاتيح
        if not KEY or not SECRET:
            return 1

    if not KEY or not SECRET:
        print("ℹ️ لا مفاتيح API — paper mode يعمل بدونها")
        if MODE == "live":
            print("❌ live يتطلب BINANCE_API_KEY و BINANCE_API_SECRET في .env")
            return 1
        return 0

    try:
        import ccxt

        exchange = ccxt.binance(
            {
                "apiKey": KEY,
                "secret": SECRET,
                "enableRateLimit": True,
                "options": {"defaultType": "spot", "adjustForTimeDifference": True},
            }
        )
        try:
            exchange.has["fetchCurrencies"] = False
        except Exception:
            pass
        if DEMO:
            try:
                exchange.enable_demo_trading(True)
                print("🔗 موجّه إلى demo-api.binance.com")
            except Exception as exc:
                print(f"⚠️ فشل enable_demo_trading: {exc}")
                return 1

        balance = exchange.fetch_balance()
        usdt = balance.get("USDT", {})
        free = usdt.get("free", 0) if isinstance(usdt, dict) else usdt
        label = "Demo" if DEMO else "Live"
        print(f"✅ مفاتيح API صالحة ({label}) — رصيد USDT: {free}")
        return 0
    except Exception as exc:
        print(f"❌ فشل التحقق من المفاتيح: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
