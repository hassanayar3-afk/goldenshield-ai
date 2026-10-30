use saqr_core::binance::http_client::BinanceHttpClient;
use saqr_core::config::env_settings::SaqrSettings;
use saqr_core::telegram::send_message::TelegramClient;
use tokio::time::{interval, Duration};

pub fn spawn_integrations_bridge(settings: SaqrSettings) {
    tokio::spawn(async move {
        if let Err(e) = run_bridge_cycle(&settings).await {
            tracing::error!("integrations bridge cycle failed: {e}");
        }
        let mut tick = interval(Duration::from_secs(900));
        tick.tick().await;
        loop {
            tick.tick().await;
            if let Err(e) = run_bridge_cycle(&settings).await {
                tracing::error!("integrations bridge cycle failed: {e}");
            }
        }
    });
}

async fn run_bridge_cycle(settings: &SaqrSettings) -> Result<(), String> {
    let binance = BinanceHttpClient::new(settings.clone());
    let binance_status = match binance.ping().await {
        Ok(()) => {
            let price = binance.ticker_price().await.unwrap_or_else(|e| e);
            let server_ms = binance
                .server_time()
                .await
                .map(|v| v.to_string())
                .unwrap_or_else(|e| e);
            format!(
                "📊 {}: <code>{}</code>\n⏱ serverTime: <code>{}</code>\n✅ Binance reachable",
                settings.symbol, price, server_ms
            )
        }
        Err(e) => format!("⚠️ Binance ping: <code>{e}</code>\n(قد يكون حظر منطقة — جرّب من VPS)"),
    };

    let tg = TelegramClient::new(settings.telegram.clone());
    if !tg.is_configured() {
        tracing::warn!("Telegram not configured");
        return Ok(());
    }

    let text = format!(
        "🦅 <b>صقر SAQR</b>\n🔗 {}\n{}\n🤖 mode: <code>{}</code>",
        binance.mode_label(),
        binance_status,
        settings.mode,
    );
    tg.send_text(&text).await?;
    tracing::info!("Telegram + Binance demo bridge notified");
    Ok(())
}
