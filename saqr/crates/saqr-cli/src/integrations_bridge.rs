use saqr_core::binance::market_public::BinancePublicMarket;
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
    let market = BinancePublicMarket::new(settings);
    let market_status = match market.ping().await {
        Ok(()) => {
            let price = market
                .price(&settings.symbol)
                .await
                .map(|p| format!("{p}"))
                .unwrap_or_else(|e| e);
            format!(
                "📊 {} (سوق حي): <code>{}</code>\n✅ Market data OK — {}",
                settings.symbol,
                price,
                market.base_url()
            )
        }
        Err(e) => format!("⚠️ Market data: <code>{e}</code>"),
    };

    let tg = TelegramClient::new(settings.telegram.clone());
    if !tg.is_configured() {
        tracing::warn!("Telegram not configured");
        return Ok(());
    }

    let exec = if settings.is_paper_trading() {
        "Paper Sandbox ($)".to_string()
    } else {
        format!("live/testnet ({})", settings.mode)
    };

    let text = format!(
        "🦅 <b>صقر SAQR v6.2.3</b>\n{}\nmode: <code>{}</code>\nتنفيذ: <code>{exec}</code>",
        market_status,
        settings.mode,
    );
    tg.send_text(&text).await?;
    tracing::info!("Telegram status (live market + paper path)");
    Ok(())
}
