use std::sync::Arc;
use std::time::Duration;

use tokio::time::interval;

use crate::runtime::SharedRuntime;
use crate::telegram_notify;

pub fn spawn_hot_loop(rt: Arc<SharedRuntime>) {
    tokio::spawn(async move {
        let mut price_tick = interval(Duration::from_secs(1));
        let report_secs = std::env::var("SAQR_INTEGRATION_INTERVAL_SECS")
            .ok()
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(300)
            .max(60);
        let mut report_tick = interval(Duration::from_secs(report_secs));
        let mut last_price: Option<f64> = None;

        loop {
            tokio::select! {
                _ = price_tick.tick() => {
                    if !rt.settings.enable_trading || !rt.bot_is_running() {
                        continue;
                    }
                    if let Ok(cur) = rt.market.price(&rt.settings.symbol).await {
                        if let Some(prev) = last_price {
                            let shock = ((cur - prev) / prev).abs();
                            if shock >= 0.01 {
                                tracing::info!("Live BTC shock {:.2}%", shock * 100.0);
                            }
                        }
                        last_price = Some(cur);
                    }
                    let _ = rt.refresh_mirror().await;
                }
                _ = report_tick.tick() => {
                    telegram_notify::periodic_report(&rt).await;
                }
            }
        }
    });
}
