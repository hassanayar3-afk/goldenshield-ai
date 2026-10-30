use std::sync::Arc;

use crate::runtime::SharedRuntime;
use crate::telegram_panel;

pub fn spawn_telegram_control_panel(rt: Arc<SharedRuntime>) {
    if !rt.settings.telegram_control_panel {
        return;
    }
    if !rt.telegram.is_configured() {
        tracing::warn!("Telegram control panel skipped — bot token / chat id missing");
        return;
    }
    tracing::info!(
        "Telegram dashboard UI (inline keyboard) every {}s",
        rt.settings.signal_interval_secs
    );
    telegram_panel::spawn_panel_refresh(rt);
}
