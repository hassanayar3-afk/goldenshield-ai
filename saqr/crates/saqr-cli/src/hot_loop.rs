use std::sync::Arc;
use std::time::Duration;

use tokio::time::interval;

use crate::runtime::SharedRuntime;
use crate::telegram_notify;

pub fn spawn_hot_loop(rt: Arc<SharedRuntime>) {
    tokio::spawn(async move {
        let mut price_tick = interval(Duration::from_secs(1));
        let mut last_price: Option<f64> = None;
        let control_panel = rt.settings.telegram_control_panel;
        if control_panel {
            loop {
                price_tick.tick().await;
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
        }

        let report_secs = rt.settings.integration_interval_secs.max(60);
        let mut report_tick = interval(Duration::from_secs(report_secs));
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
