"""مراقبة صحة APIs — Binance والإعدادات."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config.settings import CONFIG_DIR, get_settings
from data.connection_monitor import ConnectionMonitor


@dataclass(frozen=True)
class WatchdogResult:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


class ApiWatchdog:
    def run(self, connection_monitor: ConnectionMonitor | None = None) -> WatchdogResult:
        settings = get_settings()
        checks: dict[str, bool] = {}
        failures: list[str] = []

        checks["trading_pairs"] = bool(settings.trading_pairs)
        if not checks["trading_pairs"]:
            failures.append("قائمة أزواج التداول فارغة")

        checks["execution_mode"] = settings.execution_mode in {"paper", "live"}
        if not checks["execution_mode"]:
            failures.append(f"وضع تنفيذ غير صالح: {settings.execution_mode}")

        if settings.execution_mode == "live":
            has_keys = bool(settings.binance_api_key and settings.binance_api_secret)
            checks["binance_keys"] = has_keys
            if not has_keys:
                failures.append("وضع live يتطلب BINANCE_API_KEY و BINANCE_API_SECRET")
            elif connection_monitor is not None:
                checks["binance_auth"] = self._verify_binance_auth(settings)
                if not checks["binance_auth"]:
                    failures.append("فشل التحقق من مفاتيح Binance API")
        else:
            checks["binance_keys"] = True

        required_configs = (
            "trading_pairs.yaml",
            "risk_params.yaml",
            "hybrid_params.yaml",
            "execution_params.yaml",
        )
        for name in required_configs:
            path = CONFIG_DIR / name
            ok = path.exists()
            checks[f"config:{name}"] = ok
            if not ok:
                failures.append(f"ملف إعدادات مفقود: {name}")

        calendar = CONFIG_DIR / "economic_calendar.yaml"
        checks["economic_calendar"] = calendar.exists()
        if not calendar.exists():
            failures.append("economic_calendar.yaml مفقود")

        if connection_monitor is not None:
            ping_ok = False
            last_err = None
            for _ in range(3):
                ping_ok = connection_monitor.heartbeat()
                if ping_ok:
                    break
                last_err = connection_monitor.last_error
                import time

                time.sleep(2)
            checks["binance_ping"] = ping_ok
            if not ping_ok:
                failures.append(
                    f"فشل ping Binance: {last_err or connection_monitor.last_error or 'غير معروف'}"
                )
        else:
            checks["binance_ping"] = True

        db_parent = Path(settings.db_path).parent
        try:
            db_parent.mkdir(parents=True, exist_ok=True)
            probe = db_parent / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            checks["db_path_writable"] = True
        except OSError as exc:
            checks["db_path_writable"] = False
            failures.append(f"مسار DB غير قابل للكتابة: {exc}")

        # فصل التحذيرات عن الأعطال الحرجة
        critical_failures = [f for f in failures if not f.startswith("تحذير")]
        return WatchdogResult(ok=not critical_failures, checks=checks, failures=failures)

    @staticmethod
    def _verify_binance_auth(settings) -> bool:
        try:
            import ccxt

            exchange = ccxt.binance(
                {
                    "apiKey": settings.binance_api_key,
                    "secret": settings.binance_api_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                }
            )
            # مفاتيح Demo Trading تعمل فقط على demo-api
            if bool(getattr(settings, "binance_demo_trading", False)):
                try:
                    exchange.enable_demo_trading(True)
                except Exception:
                    try:
                        exchange.urls["api"] = dict(exchange.urls.get("api") or {})
                        exchange.urls["api"]["public"] = "https://demo-api.binance.com/api/v3"
                        exchange.urls["api"]["private"] = "https://demo-api.binance.com/api/v3"
                    except Exception:
                        pass
            exchange.fetch_balance()
            return True
        except Exception:
            return False
