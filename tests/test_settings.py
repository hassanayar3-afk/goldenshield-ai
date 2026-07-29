from config.settings import load_settings


def test_load_settings_dev():
    settings = load_settings("dev", reload=True)
    assert settings.env == "dev"
    assert "BTC/USDT" in settings.trading_pairs
    assert settings.risk_per_trade_pct == 1.0
    assert settings.kill_switch_daily_pct == -3.0
    assert settings.loop_interval_seconds == 60
    assert settings.log_level == "DEBUG"
    assert settings.db_path == "storage/db/goldenshield_dev.db"


def test_load_settings_staging():
    settings = load_settings("staging", reload=True)
    assert settings.env == "staging"
    assert settings.log_level == "INFO"
    assert settings.db_path == "storage/db/goldenshield_staging.db"


def test_load_settings_production():
    settings = load_settings("production", reload=True)
    assert settings.env == "production"
    assert settings.log_level == "WARNING"
    assert settings.db_path == "storage/db/goldenshield.db"


def test_trading_pairs_match_defaults():
    settings = load_settings("dev", reload=True)
    # 14 عملة رقمية — Binance فقط
    assert len(settings.trading_pairs) == 14
    assert settings.trading_pairs[:3] == ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
    assert "SOL/USDT" in settings.trading_pairs
    assert "DOGE/USDT" in settings.trading_pairs
    assert all(not p.startswith(("FOREX/", "STOCK/")) for p in settings.trading_pairs)
    assert settings.news_filter_enabled is True
    assert settings.vix_threshold == 30.0
    assert settings.execution_mode == "paper"
    assert settings.paper_account_balance == 10000.0
    assert settings.max_concurrent_positions == 12
    assert settings.min_account_balance == 100.0
    assert settings.monte_carlo_simulations == 1000
