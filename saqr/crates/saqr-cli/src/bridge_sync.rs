use crate::runtime::SharedRuntime;
use crate::telegram_notify;

/// Real-time sync: refresh mirror cache then optional Telegram ack (Terminal or TG command path).
pub async fn sync_after_trade_action(rt: &SharedRuntime, source: &str, action: &str, closed: u32) {
    let mirror = rt.refresh_mirror().await;
    telegram_notify::bridge_sync_event(rt, source, action, closed, &mirror).await;
}
