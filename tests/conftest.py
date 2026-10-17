from pathlib import Path

import pytest

# متغيرات .env الحيّة التي تلوّث اختبارات الإعدادات الافتراضية
_SETTINGS_OVERRIDE_ENV = (
    "LOOP_INTERVAL_SECONDS",
    "DB_PATH",
    "ENV",
    "MANUAL_ENTRY_REQUIRED",
    "AUTO_ENTRY_MIN_PERCENT",
    "EXECUTION_MODE",
    "MAX_CONCURRENT_POSITIONS",
    "BINANCE_DEMO_TRADING",
    "EXECUTION_BACKEND",
)


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def stub_integration_exchange(request, monkeypatch):
    """منع اختبارات integration من الاعتماد على Binance الحي (451/geo)."""
    if request.node.get_closest_marker("integration") is None:
        return

    from data.models.candle import Candle

    class _FakeExchange:
        def load_markets(self, reload: bool = False) -> dict:
            return {
                "BTC/USDT": {
                    "limits": {"amount": {"min": 0.0001}, "cost": {"min": 5.0}},
                },
                "ETH/USDT": {
                    "limits": {"amount": {"min": 0.0001}, "cost": {"min": 5.0}},
                },
                "BNB/USDT": {
                    "limits": {"amount": {"min": 0.0001}, "cost": {"min": 5.0}},
                },
            }

        def market(self, symbol: str) -> dict:
            return self.load_markets().get(
                symbol,
                {"limits": {"amount": {"min": 0.0001}, "cost": {"min": 5.0}}},
            )

        def amount_to_precision(self, symbol: str, amount: float) -> float:
            return float(amount)

        def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100, **kwargs):
            base = 100.0
            rows = []
            for index in range(limit):
                price = base + index * 0.5
                rows.append(
                    [
                        1_700_000_000_000 + index * 60_000,
                        price,
                        price + 1,
                        price - 1,
                        price + 0.2,
                        1000.0 + index,
                    ]
                )
            return rows

        def fetch_ticker(self, symbol: str) -> dict:
            return {"last": 100.0, "close": 100.0}

        def fetch_balance(self) -> dict:
            return {"USDT": {"free": 10_000.0, "total": 10_000.0}}

    fake = _FakeExchange()

    def _get_fake():
        return fake

    monkeypatch.setattr("data.exchange_client.get_exchange", _get_fake)
    monkeypatch.setattr("data.ohlcv_fetcher.get_exchange", _get_fake)
    monkeypatch.setattr("data.connection_utils.get_exchange", _get_fake, raising=False)


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    """إعادة ضبط الإعدادات وعزل الاختبارات عن .env التشغيلي."""
    import config.settings as settings_module

    settings_module._settings = None
    # منع load_dotenv من إعادة حقن قيم التشغيل أثناء الاختبارات
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *args, **kwargs: False)
    for key in _SETTINGS_OVERRIDE_ENV:
        monkeypatch.delenv(key, raising=False)
    yield
    settings_module._settings = None
