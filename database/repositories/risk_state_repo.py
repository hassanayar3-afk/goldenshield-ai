"""حفظ/تحميل حالة المخاطر عبر app_config."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from database.repositories.config_repo import ConfigRepository
from risk.state import RiskState

RISK_STATE_KEY = "risk_state"
RISK_SESSION_DAY_KEY = "risk_session_day"


def serialize_risk_state(state: RiskState) -> str:
    payload = {
        "session_start_balance": state.session_start_balance,
        "current_balance": state.current_balance,
        "daily_trades": state.daily_trades,
        "consecutive_losses": state.consecutive_losses,
        "consecutive_wins": getattr(state, "consecutive_wins", 0),
        "daily_profit": state.daily_profit,
        "daily_loss": state.daily_loss,
        "cooldown_until": state.cooldown_until.isoformat() if state.cooldown_until else None,
        "kill_switch_active": state.kill_switch_active,
        "hc_daily_trades": state.hc_daily_trades,
        "hc_consecutive_wins": state.hc_consecutive_wins,
        "hc_last_trade_at": (
            state.hc_last_trade_at.isoformat() if state.hc_last_trade_at else None
        ),
        "trade_open_timestamps": [
            ts.isoformat() for ts in state.trade_open_timestamps
        ],
        "post_trade_cooldown_until": (
            state.post_trade_cooldown_until.isoformat()
            if state.post_trade_cooldown_until
            else None
        ),
        "last_updated": state.last_updated.isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False)


def deserialize_risk_state(raw: str) -> RiskState:
    data = json.loads(raw)
    cooldown = data.get("cooldown_until")
    hc_last = data.get("hc_last_trade_at")
    post_cd = data.get("post_trade_cooldown_until")
    last_updated = data.get("last_updated")
    open_ts_raw = data.get("trade_open_timestamps") or []
    open_ts: list[datetime] = []
    for item in open_ts_raw:
        try:
            open_ts.append(datetime.fromisoformat(str(item)))
        except ValueError:
            continue
    return RiskState(
        session_start_balance=float(data["session_start_balance"]),
        current_balance=float(data["current_balance"]),
        daily_trades=int(data.get("daily_trades", 0)),
        consecutive_losses=int(data.get("consecutive_losses", 0)),
        consecutive_wins=int(data.get("consecutive_wins", 0)),
        daily_profit=float(data.get("daily_profit", 0.0)),
        daily_loss=float(data.get("daily_loss", 0.0)),
        cooldown_until=datetime.fromisoformat(cooldown) if cooldown else None,
        kill_switch_active=bool(data.get("kill_switch_active", False)),
        hc_daily_trades=int(data.get("hc_daily_trades", 0)),
        hc_consecutive_wins=int(data.get("hc_consecutive_wins", 0)),
        hc_last_trade_at=datetime.fromisoformat(hc_last) if hc_last else None,
        trade_open_timestamps=open_ts,
        post_trade_cooldown_until=(
            datetime.fromisoformat(post_cd) if post_cd else None
        ),
        last_updated=datetime.fromisoformat(last_updated) if last_updated else datetime.now(timezone.utc),
    )


def save_risk_state(repo: ConfigRepository, state: RiskState, session_day: date | None = None) -> None:
    repo.set(RISK_STATE_KEY, serialize_risk_state(state))
    if session_day is not None:
        repo.set(RISK_SESSION_DAY_KEY, session_day.isoformat())


def load_risk_state(repo: ConfigRepository) -> tuple[RiskState | None, date | None]:
    raw = repo.get(RISK_STATE_KEY)
    if not raw:
        return None, None
    try:
        state = deserialize_risk_state(raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None, None
    day_raw = repo.get(RISK_SESSION_DAY_KEY)
    session_day = None
    if day_raw:
        try:
            session_day = date.fromisoformat(day_raw)
        except ValueError:
            session_day = None
    return state, session_day
