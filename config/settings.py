from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from core.exceptions import ConfigurationError

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent
VALID_ENVS = frozenset({"dev", "staging", "production"})
ENV_ALIASES = {"prod": "production"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"ملف الإعدادات غير موجود: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = base.copy()
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_db_path(raw: str) -> str:
    """مسار DB نسبي في الإعدادات — يُحلّ مطلقاً عند فتح الاتصال."""
    text = (raw or "storage/db/goldenshield.db").strip() or "storage/db/goldenshield.db"
    path = Path(text)
    if path.is_absolute():
        return str(path).replace("\\", "/")
    return str(path).replace("\\", "/")


def resolve_db_path_absolute(db_path: str) -> Path:
    """حل مسار DB للتشغيل الفعلي (workspace أو GOLDENSHIELD_OFFICIAL_ROOT)."""
    path = Path((db_path or "storage/db/goldenshield.db").strip())
    if path.is_absolute():
        return path
    official = Path(
        (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    )
    try:
        if official.is_dir():
            return (official / path).resolve()
    except Exception:
        pass
    return (BASE_DIR / path).resolve()


@dataclass(frozen=True)
class Settings:
    env: str
    trading_pairs: list[str]
    risk_per_trade_pct: float
    kill_switch_daily_pct: float
    gradual_growth_threshold_pct: float
    max_daily_trades: int
    max_trades_per_hour: int
    post_trade_cooldown_minutes: int
    kill_zones_enabled: bool
    kill_zones_sessions: tuple[str, ...]
    quality_gates_enabled: bool
    volume_spike_multiplier: float
    max_slippage_pct: float
    trailing_stop_enabled: bool
    trailing_stop_factor: float
    loss_streak_limit: int
    cooldown_hours: int
    loop_interval_seconds: int
    log_level: str
    db_path: str
    binance_api_key: str | None
    binance_api_secret: str | None
    binance_api_key_2: str | None
    binance_api_secret_2: str | None
    binance_demo_trading: bool
    telegram_token: str | None
    telegram_chat_id: str | None
    telegram_bot_username: str | None
    telegram_backup_channel_id: str | None
    telegram_send_cycle_signals: bool
    telegram_signals_only: bool
    telegram_signal_min_percent: int
    discord_bot_token: str | None
    discord_webhook_url: str | None
    discord_channel_id: str | None
    discord_signals_only: bool
    manual_entry_required: bool
    auto_entry_min_percent: int
    news_filter_enabled: bool
    news_blackout_minutes: int
    vix_threshold: float
    bonds_yield_spike_pct: float
    fear_greed_extreme_low: int
    fear_greed_extreme_high: int
    whale_wall_multiplier: float
    institutional_min_levels: int
    sentiment_anomaly_threshold: float
    execution_mode: str
    paper_account_balance: float
    default_sl_pct: float
    default_rr_ratio: float
    dark_pool_max_chunk_usdt: float
    max_concurrent_positions: int
    # 0 = يدوي بلا سقف عدد (التلقائي يبقى على max_concurrent + قواعد الشرائح)
    manual_max_concurrent_positions: int
    partial_exit_pct: float
    breakeven_enabled: bool
    correlation_groups: tuple[tuple[str, ...], ...]
    min_account_balance: float
    monte_carlo_simulations: int
    monte_carlo_min_win_rate: float
    execution_backend: str
    trial_mode: bool
    trial_journal_enabled: bool
    bot_admin_full_access: bool
    high_conviction_mode: bool
    standard_bonus_profile: bool
    high_conviction_config: dict
    standard_bonus_config: dict
    # —— v1.1.2 Pre-Execution / Emergency SL (defaults آمنة) ——
    pre_execution_gate_enabled: bool
    emergency_protocols_enabled: bool
    emergency_atr_sl_enabled: bool
    emergency_atr_mult: float
    emergency_atr_period: int
    emergency_atr_timeframe: str
    risk_distance_filter_enabled: bool
    risk_distance_max_sl_pct: float
    sl_rr_lock_enabled: bool
    sl_rr_lock_ratio: float
    volatility_guard_enabled: bool
    volatility_guard_expand_mult: float
    # —— حماية التذاكر / إدارة أثناء الإيقاف ——
    require_sl_on_all_chunks: bool
    close_naked_tickets: bool
    manage_positions_during_halt: bool
    # —— v1.2 مؤسسي (افتراضي: معطّل — استقرار أولاً) ——
    adx_filter_enabled: bool
    adx_min_trend: float
    adx_period: int
    adx_timeframe: str
    market_correlation_filter_enabled: bool
    panic_mode_block_long: bool
    partial_scaling_enabled: bool
    partial_scaling_initial_pct: float
    partial_scaling_add_pct: float
    partial_scaling_trigger_r: float
    micro_simulation_enabled: bool
    micro_simulation_lookback: int
    micro_simulation_min_winrate: float
    profit_cap_enabled: bool
    profit_cap_daily_pct: float
    smart_trade_report_enabled: bool
    # —— v1.3 قاموس الأعلام المؤسسية ——
    institutional_v13: dict


_settings: Settings | None = None


def load_settings(env: str | None = None, *, reload: bool = False) -> Settings:
    global _settings

    if _settings is not None and not reload:
        return _settings

    load_dotenv(BASE_DIR / ".env")

    env_name = (env or os.getenv("ENV", "dev")).strip().lower()
    env_name = ENV_ALIASES.get(env_name, env_name)
    if env_name not in VALID_ENVS:
        raise ConfigurationError(
            f"بيئة غير صالحة: {env_name}. المسموح: {', '.join(sorted(VALID_ENVS))}"
        )

    trading_config = _load_yaml(CONFIG_DIR / "trading_pairs.yaml")
    risk_config = _load_yaml(CONFIG_DIR / "risk_params.yaml")
    hybrid_config = _load_yaml(CONFIG_DIR / "hybrid_params.yaml")
    execution_config = _load_yaml(CONFIG_DIR / "execution_params.yaml")
    trial_config = _load_yaml(CONFIG_DIR / "trial_params.yaml")
    hc_config = _load_yaml(CONFIG_DIR / "high_conviction_protocol.yaml")
    bonus_config = _load_yaml(CONFIG_DIR / "standard_bonus_profile.yaml")
    env_config = _load_yaml(CONFIG_DIR / "environments" / f"{env_name}.yaml")

    merged = _deep_merge(
        {
            "trading": trading_config,
            "risk": risk_config,
            "hybrid": hybrid_config,
            "execution": execution_config,
            "trial": trial_config,
            "app": {"loop_interval_seconds": 60, "log_level": "INFO"},
            "database": {"path": "storage/db/goldenshield.db"},
        },
        env_config,
    )

    pairs = merged.get("trading", {}).get("pairs", [])
    if not pairs:
        raise ConfigurationError("قائمة أزواج التداول فارغة في trading_pairs.yaml")

    risk = merged.get("risk", {})
    hybrid = merged.get("hybrid", {})
    execution = merged.get("execution", {})
    trial = merged.get("trial", trial_config)
    app = merged.get("app", {})
    database = merged.get("database", {})

    _settings = Settings(
        env=env_name,
        trading_pairs=list(pairs),
        risk_per_trade_pct=float(risk.get("risk_per_trade_pct", 1.0)),
        kill_switch_daily_pct=float(risk.get("kill_switch_daily_pct", -3.0)),
        gradual_growth_threshold_pct=float(risk.get("gradual_growth_threshold_pct", 20.0)),
        max_daily_trades=int(risk.get("max_daily_trades", 10)),
        max_trades_per_hour=int(risk.get("max_trades_per_hour", 3)),
        post_trade_cooldown_minutes=int(risk.get("post_trade_cooldown_minutes", 20)),
        kill_zones_enabled=bool(risk.get("kill_zones_enabled", True)),
        kill_zones_sessions=tuple(
            str(s) for s in risk.get(
                "kill_zones_sessions",
                ["london", "london_ny_overlap", "new_york"],
            )
        ),
        quality_gates_enabled=bool(risk.get("quality_gates_enabled", True)),
        volume_spike_multiplier=float(risk.get("volume_spike_multiplier", 1.5)),
        max_slippage_pct=float(risk.get("max_slippage_pct", 0.1)),
        trailing_stop_enabled=bool(risk.get("trailing_stop_enabled", True)),
        trailing_stop_factor=float(risk.get("trailing_stop_factor", 0.5)),
        loss_streak_limit=int(risk.get("loss_streak_limit", 3)),
        cooldown_hours=int(risk.get("cooldown_hours", 24)),
        loop_interval_seconds=int(
            os.getenv("LOOP_INTERVAL_SECONDS") or app.get("loop_interval_seconds", 4)
        ),
        log_level=str(app.get("log_level", "INFO")),
        db_path=_resolve_db_path(
            str(os.getenv("DB_PATH") or database.get("path", "storage/db/goldenshield.db"))
        ),
        binance_api_key=os.getenv("BINANCE_API_KEY") or None,
        binance_api_secret=os.getenv("BINANCE_API_SECRET") or None,
        binance_api_key_2=os.getenv("BINANCE_API_KEY_2") or None,
        binance_api_secret_2=os.getenv("BINANCE_API_SECRET_2") or None,
        binance_demo_trading=os.getenv("BINANCE_DEMO_TRADING", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        telegram_token=os.getenv("TELEGRAM_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        telegram_bot_username=os.getenv("TELEGRAM_BOT_USERNAME") or None,
        telegram_backup_channel_id=os.getenv("TELEGRAM_BACKUP_CHANNEL_ID") or None,
        telegram_send_cycle_signals=os.getenv("TELEGRAM_SEND_CYCLE_SIGNALS", "true")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        # true = تيليجرام للإشارات/الصفقات فقط (بدون قائمة تشغيل أو تقارير)
        telegram_signals_only=os.getenv("TELEGRAM_SIGNALS_ONLY", "true")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        # إرسال إشارات تيليجرام من 70/100 فما فوق (درجة 7+ — هجين يدوي/تلقائي)
        telegram_signal_min_percent=int(os.getenv("TELEGRAM_SIGNAL_MIN_PERCENT", "70")),
        discord_bot_token=os.getenv("DISCORD_BOT_TOKEN") or None,
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL") or None,
        discord_channel_id=os.getenv("DISCORD_CHANNEL_ID") or None,
        discord_signals_only=os.getenv("DISCORD_SIGNALS_ONLY", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        # false = هجين: تلقائي عند ≥ AUTO_ENTRY | يدوي عبر تيليجرام للدرجات الأقل
        manual_entry_required=os.getenv("MANUAL_ENTRY_REQUIRED", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        # دخول تلقائي من 90/100 فما فوق (درجة 9–10 فقط)
        auto_entry_min_percent=int(os.getenv("AUTO_ENTRY_MIN_PERCENT", "90")),
        news_filter_enabled=bool(hybrid.get("news_filter_enabled", True)),
        news_blackout_minutes=int(hybrid.get("news_blackout_minutes", 30)),
        vix_threshold=float(hybrid.get("vix_threshold", 30.0)),
        bonds_yield_spike_pct=float(hybrid.get("bonds_yield_spike_pct", 3.0)),
        fear_greed_extreme_low=int(hybrid.get("fear_greed_extreme_low", 20)),
        fear_greed_extreme_high=int(hybrid.get("fear_greed_extreme_high", 80)),
        whale_wall_multiplier=float(hybrid.get("whale_wall_multiplier", 3.0)),
        institutional_min_levels=int(hybrid.get("institutional_min_levels", 2)),
        sentiment_anomaly_threshold=float(hybrid.get("sentiment_anomaly_threshold", 2.0)),
        execution_mode=str(
            os.getenv("EXECUTION_MODE") or execution.get("execution_mode", "paper")
        ).strip().lower(),
        paper_account_balance=float(execution.get("paper_account_balance", 10000.0)),
        default_sl_pct=float(execution.get("default_sl_pct", 0.03)),
        default_rr_ratio=float(execution.get("default_rr_ratio", 3.0)),
        dark_pool_max_chunk_usdt=float(execution.get("dark_pool_max_chunk_usdt", 500.0)),
        max_concurrent_positions=int(
            os.getenv("MAX_CONCURRENT_POSITIONS")
            or execution.get("max_concurrent_positions", 12)
        ),
        manual_max_concurrent_positions=int(
            os.getenv("MANUAL_MAX_CONCURRENT_POSITIONS")
            or execution.get("manual_max_concurrent_positions", 0)
        ),
        partial_exit_pct=float(execution.get("partial_exit_pct", 0.5)),
        breakeven_enabled=bool(execution.get("breakeven_enabled", True)),
        correlation_groups=tuple(
            tuple(group) for group in execution.get("correlation_groups", [])
        ),
        min_account_balance=float(risk.get("min_account_balance", 100.0)),
        monte_carlo_simulations=int(risk.get("monte_carlo_simulations", 1000)),
        monte_carlo_min_win_rate=float(risk.get("monte_carlo_min_win_rate", 0.35)),
        # Binance فقط — أي قيمة EXECUTION_BACKEND أخرى تُتجاهل
        execution_backend="binance",
        trial_mode=os.getenv("TRIAL_MODE", str(trial.get("trial_mode", "false")))
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        trial_journal_enabled=os.getenv(
            "TRIAL_JOURNAL_ENABLED", str(trial.get("trial_journal_enabled", "true"))
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        bot_admin_full_access=os.getenv("BOT_ADMIN_FULL_ACCESS", "true")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        high_conviction_mode=os.getenv("HIGH_CONVICTION_MODE", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        standard_bonus_profile=os.getenv("STANDARD_BONUS_PROFILE", "false")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        high_conviction_config=hc_config,
        standard_bonus_config=bonus_config,
        pre_execution_gate_enabled=os.getenv(
            "PRE_EXECUTION_GATE_ENABLED",
            str(risk.get("pre_execution_gate_enabled", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        emergency_protocols_enabled=os.getenv(
            "EMERGENCY_PROTOCOLS_ENABLED",
            str(risk.get("emergency_protocols_enabled", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        emergency_atr_sl_enabled=os.getenv(
            "EMERGENCY_ATR_SL_ENABLED",
            str(risk.get("emergency_atr_sl_enabled", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        emergency_atr_mult=float(
            os.getenv("EMERGENCY_ATR_MULT", risk.get("emergency_atr_mult", 1.5))
        ),
        emergency_atr_period=int(
            os.getenv("EMERGENCY_ATR_PERIOD", risk.get("emergency_atr_period", 14))
        ),
        emergency_atr_timeframe=str(
            os.getenv(
                "EMERGENCY_ATR_TIMEFRAME",
                risk.get("emergency_atr_timeframe", "15m"),
            )
        ),
        risk_distance_filter_enabled=os.getenv(
            "RISK_DISTANCE_FILTER_ENABLED",
            str(risk.get("risk_distance_filter_enabled", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        risk_distance_max_sl_pct=float(
            os.getenv(
                "RISK_DISTANCE_MAX_SL_PCT",
                risk.get("risk_distance_max_sl_pct", 0.05),
            )
        ),
        sl_rr_lock_enabled=os.getenv(
            "SL_RR_LOCK_ENABLED",
            str(risk.get("sl_rr_lock_enabled", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        sl_rr_lock_ratio=float(
            os.getenv("SL_RR_LOCK_RATIO", risk.get("sl_rr_lock_ratio", 3.0))
        ),
        volatility_guard_enabled=os.getenv(
            "VOLATILITY_GUARD_ENABLED",
            str(risk.get("volatility_guard_enabled", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        volatility_guard_expand_mult=float(
            os.getenv(
                "VOLATILITY_GUARD_EXPAND_MULT",
                risk.get("volatility_guard_expand_mult", 1.5),
            )
        ),
        require_sl_on_all_chunks=os.getenv(
            "REQUIRE_SL_ON_ALL_CHUNKS",
            str(risk.get("require_sl_on_all_chunks", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        close_naked_tickets=os.getenv(
            "CLOSE_NAKED_TICKETS",
            str(risk.get("close_naked_tickets", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        manage_positions_during_halt=os.getenv(
            "MANAGE_POSITIONS_DURING_HALT",
            str(risk.get("manage_positions_during_halt", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        adx_filter_enabled=os.getenv(
            "ADX_FILTER_ENABLED", str(risk.get("adx_filter_enabled", "false"))
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        adx_min_trend=float(os.getenv("ADX_MIN_TREND", risk.get("adx_min_trend", 20))),
        adx_period=int(os.getenv("ADX_PERIOD", risk.get("adx_period", 14))),
        adx_timeframe=str(
            os.getenv("ADX_TIMEFRAME", risk.get("adx_timeframe", "15m"))
        ),
        market_correlation_filter_enabled=os.getenv(
            "MARKET_CORRELATION_FILTER_ENABLED",
            str(risk.get("market_correlation_filter_enabled", "false")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        panic_mode_block_long=os.getenv(
            "PANIC_MODE_BLOCK_LONG",
            str(risk.get("panic_mode_block_long", "true")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        partial_scaling_enabled=os.getenv(
            "PARTIAL_SCALING_ENABLED",
            str(risk.get("partial_scaling_enabled", "false")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        partial_scaling_initial_pct=float(
            os.getenv(
                "PARTIAL_SCALING_INITIAL_PCT",
                risk.get("partial_scaling_initial_pct", 50),
            )
        ),
        partial_scaling_add_pct=float(
            os.getenv(
                "PARTIAL_SCALING_ADD_PCT",
                risk.get("partial_scaling_add_pct", 50),
            )
        ),
        partial_scaling_trigger_r=float(
            os.getenv(
                "PARTIAL_SCALING_TRIGGER_R",
                risk.get("partial_scaling_trigger_r", 0.5),
            )
        ),
        micro_simulation_enabled=os.getenv(
            "MICRO_SIMULATION_ENABLED",
            str(risk.get("micro_simulation_enabled", "false")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        micro_simulation_lookback=int(
            os.getenv(
                "MICRO_SIMULATION_LOOKBACK",
                risk.get("micro_simulation_lookback", 10),
            )
        ),
        micro_simulation_min_winrate=float(
            os.getenv(
                "MICRO_SIMULATION_MIN_WINRATE",
                risk.get("micro_simulation_min_winrate", 0.5),
            )
        ),
        profit_cap_enabled=os.getenv(
            "PROFIT_CAP_ENABLED",
            str(risk.get("profit_cap_enabled", "false")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        profit_cap_daily_pct=float(
            os.getenv("PROFIT_CAP_DAILY_PCT", risk.get("profit_cap_daily_pct", 3.0))
        ),
        smart_trade_report_enabled=os.getenv(
            "SMART_TRADE_REPORT_ENABLED",
            str(risk.get("smart_trade_report_enabled", "false")),
        )
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        institutional_v13=dict(risk.get("institutional_v13") or {}),
    )
    try:
        from risk.iron_protocol import apply_iron_protocol

        _settings = apply_iron_protocol(_settings)
    except Exception:
        pass
    return _settings


def get_settings() -> Settings:
    if _settings is None:
        return load_settings()
    return _settings
