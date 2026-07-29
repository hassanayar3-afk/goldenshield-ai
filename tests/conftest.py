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
)


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


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
