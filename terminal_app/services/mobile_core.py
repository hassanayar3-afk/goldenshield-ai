"""واجهة توافق — استخدم alerts_queue / binance_mirror / bot_bridge مباشرة."""

from __future__ import annotations

from terminal_app.services import alerts_queue as aq
from terminal_app.services import binance_mirror as bm
from terminal_app.services import bot_bridge as bb

_utc = aq.utc
_load_json = aq.load_json
_save_json = aq.save_json
_devices = aq.devices
_save_devices = aq.save_devices
_prune_devices = aq.prune_devices
_alerts = aq.alerts
_push_alert = aq.push_alert

_db = bb.db
_risk_state = bb.risk_state
_rules_payload = bb.rules_payload
_status = bb.status
_positions = bb.positions
_history = bb.history
_db_open_trades = bb.db_open_trades
_signals_live = bb.signals_live
_parse_signals_from_log = bb.parse_signals_from_log
_parse_signal_line = bb.parse_signal_line
_maybe_alert_signal = bb.maybe_alert_signal
_score_bucket = bb.score_bucket
_last_score_bucket = bb._last_score_bucket  # noqa: SLF001
_write_heartbeat = bb.write_heartbeat
_mark_trade_closed = bb.mark_trade_closed
_tunnel_url = bb.tunnel_url
_discord_cfg_public = bb.discord_cfg_public
_battalion_payload = bb.battalion_payload
_stack_payload = bb.stack_payload
_save_discord_config = bb.save_discord_config

_binance_snapshot = bm.binance_snapshot
_account_from_status = bm.account_from_status
_close_positions = bm.close_positions
_live_prices = bm.live_prices
