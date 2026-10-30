use std::sync::Arc;
use std::time::Duration;

use tokio::time::interval;

use crate::market_signals;
use crate::runtime::SharedRuntime;

pub fn spawn_telegram_control_panel(rt: Arc<SharedRuntime>) {
    if !rt.settings.telegram_control_panel {
        return;
    }
    if !rt.telegram.is_configured() {
        tracing::warn!("Telegram control panel skipped — bot token / chat id missing");
        return;
    }
    tokio::spawn(async move {
        run_signal_board(rt).await;
    });
}

async fn run_signal_board(rt: Arc<SharedRuntime>) {
    let secs = rt.settings.signal_interval_secs.max(2);
    let mut tick = interval(Duration::from_secs(secs));
    tick.tick().await;

    let _ = rt
        .telegram
        .send_text(
            "🦅 <b>صقر — لوحة Telegram</b>\n\
✅ Binance ⇄ Telegram مباشر\n\
📡 الإشارات تتحدّث كل 3 ثوانٍ\n\
🎛 لوحة الويب معطّلة — استخدم /help",
        )
        .await;

    tracing::info!(
        "Telegram control panel active (signals every {}s, web={})",
        secs,
        rt.settings.web_enabled
    );

    loop {
        tick.tick().await;
        if !rt.telegram.is_configured() {
            continue;
        }
        let text = match build_board_text(&rt).await {
            Ok(t) => t,
            Err(e) => {
                tracing::debug!("signal board: {e}");
                continue;
            }
        };
        let mid = *rt.telegram_board_message_id.lock();
        if let Some(mid) = mid {
            if rt.telegram.edit_text(mid, &text).await.is_err() {
                *rt.telegram_board_message_id.lock() = None;
            }
        } else {
            match rt.telegram.send_text_return_id(&text).await {
                Ok(mid) => *rt.telegram_board_message_id.lock() = Some(mid),
                Err(e) => tracing::warn!("telegram board send: {e}"),
            }
        }
    }
}

async fn build_board_text(rt: &SharedRuntime) -> Result<String, String> {
    let sym = rt.settings.symbol.clone();
    let px = rt
        .market
        .price(&sym)
        .await
        .map_err(|e| e.to_string())?;
    let mirror = rt.refresh_mirror().await;
    let signals = market_signals::fetch_live_signals(rt, "15m").await;

    let mut lines = format!(
        "🦅 <b>صقر SAQR v6.2.3 — لوحة Telegram</b>\n\
📡 Binance: <code>{}</code>\n\
💰 Paper: <code>{:.2} $</code> | مفتوحة: <code>{}</code> | يوم: <code>{:+.2}%</code>\n\
<b>{sym}</b> @ <code>{px:.2}</code> | بوت: <code>{}</code>\n\
━━━━━━━━━━━━━━━━\n\
<b>إشارات حية (15m)</b> — تحديث كل {}ث\n",
        rt.settings.market_rest_url,
        mirror.total_balance_usd,
        mirror.open_positions_count,
        mirror.daily_profit_pct,
        if rt.bot_is_running() { "نشط ✅" } else { "متوقف ⏸" },
        rt.settings.signal_interval_secs,
    );

    for s in signals.iter().take(5) {
        let arrow = if s.direction == "BUY" { "🟢" } else { "🔴" };
        lines.push_str(&format!(
            "{arrow} <code>{}</code> {} · <code>{:.4}</code> · RSI <code>{:.0}</code> · {}%\n",
            s.pair, s.direction, s.price, s.rsi, s.strength
        ));
    }

    lines.push_str(
        "\n<b>أوامر:</b> /buy /price /status /close_win /close_loss /emergency /pause /resume",
    );
    Ok(lines)
}
