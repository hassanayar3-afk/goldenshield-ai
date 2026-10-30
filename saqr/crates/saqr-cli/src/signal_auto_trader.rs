use std::collections::HashSet;
use std::sync::Arc;
use std::time::Duration;

use tokio::time::interval;

use crate::control_actions;
use crate::market_signals;
use crate::runtime::SharedRuntime;

pub fn spawn_signal_auto_trader(rt: Arc<SharedRuntime>) {
    if !rt.settings.auto_paper_signals {
        tracing::info!("Auto paper signal entries disabled (SAQR_AUTO_PAPER_SIGNALS=false)");
        return;
    }
    if !rt.settings.is_paper_trading() && !rt.settings.live_execution_enabled() {
        tracing::warn!("Auto signal trader requires paper or live/testnet trading enabled");
        return;
    }
    tokio::spawn(async move {
        run_auto_trader(rt).await;
    });
}

async fn run_auto_trader(rt: Arc<SharedRuntime>) {
    let secs = rt.settings.signal_interval_secs.max(2);
    let mut tick = interval(Duration::from_secs(secs));
    tick.tick().await;
    tracing::info!(
        "Auto paper signal trader ON — min strength {}%, risk {}%, max open {}",
        rt.settings.auto_signal_min_strength,
        rt.settings.auto_signal_risk_pct,
        rt.settings.auto_max_open_positions
    );

    loop {
        tick.tick().await;
        if !rt.settings.enable_trading || !rt.bot_is_running() {
            continue;
        }
        let mirror = rt.refresh_mirror().await;
        if mirror.open_positions_count >= rt.settings.auto_max_open_positions {
            continue;
        }
        let open_syms: HashSet<String> = mirror
            .positions
            .iter()
            .map(|p| p.symbol.clone())
            .collect();

        let signals = market_signals::fetch_live_signals(&rt, "15m").await;
        let min = rt.settings.auto_signal_min_strength;
        let risk = rt.settings.auto_signal_risk_pct;

        for sig in signals {
            if sig.direction != "BUY" || sig.strength < min {
                continue;
            }
            if open_syms.contains(&sig.symbol) {
                continue;
            }
            if rt.auto_entered_symbols.lock().contains(&sig.symbol) {
                continue;
            }
            if mirror.open_positions_count >= rt.settings.auto_max_open_positions {
                break;
            }
            let (code, body) =
                control_actions::enter_market(&rt, &sig.symbol, risk, "auto_signal").await;
            if code.is_success() {
                rt.auto_entered_symbols.lock().insert(sig.symbol.clone());
                tracing::info!(
                    "Auto paper entry {} strength={}% price={:.4}",
                    sig.symbol,
                    sig.strength,
                    sig.price
                );
            } else {
                tracing::debug!(
                    "Auto entry skipped {}: {}",
                    sig.symbol,
                    body.get("error").and_then(|v| v.as_str()).unwrap_or("?")
                );
            }
        }
    }
}
