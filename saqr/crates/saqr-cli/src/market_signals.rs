use saqr_core::binance::market_public::{closes_from_klines, rsi_from_closes};

use crate::runtime::SharedRuntime;

/// Default seven pairs (overridden by SAQR_WATCH_SYMBOLS in .env).
pub const DEFAULT_WATCH_SYMBOLS: &[&str] = &[
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
];

pub fn watch_symbols(rt: &SharedRuntime) -> Vec<String> {
    if rt.settings.watch_symbols.is_empty() {
        DEFAULT_WATCH_SYMBOLS.iter().map(|s| (*s).to_string()).collect()
    } else {
        rt.settings.watch_symbols.clone()
    }
}

#[derive(Debug, Clone)]
pub struct LiveSignal {
    pub symbol: String,
    pub pair: String,
    pub direction: String,
    pub strength: i32,
    pub price: f64,
    pub rsi: f64,
}

pub async fn fetch_live_signals(rt: &SharedRuntime, interval: &str) -> Vec<LiveSignal> {
    let symbols = watch_symbols(rt);
    let mut out = Vec::new();
    for sym in &symbols {
        let klines = match rt.market.klines(sym, interval, 60).await {
            Ok(k) => k,
            Err(e) => {
                tracing::debug!("signals klines {sym}: {e}");
                continue;
            }
        };
        let closes = closes_from_klines(&klines);
        let rsi = rsi_from_closes(&closes, 14).unwrap_or(50.0);
        let last = *closes.last().unwrap_or(&0.0);
        let prev = closes
            .get(closes.len().saturating_sub(5))
            .copied()
            .unwrap_or(last);
        let direction = if last >= prev { "BUY" } else { "SELL" };
        let momentum = (last - prev).abs() / last.max(1.0) * 8000.0;
        let strength = (((rsi - 50.0).abs() + momentum).min(28.0) + 72.0) as i32;
        let strength = strength.clamp(72, 97);
        let base = sym.strip_suffix("USDT").unwrap_or(sym.as_str());
        out.push(LiveSignal {
            symbol: sym.clone(),
            pair: format!("{base}/USDT"),
            direction: direction.into(),
            strength,
            price: last,
            rsi,
        });
    }
    if out.is_empty() {
        let fallback = rt.settings.symbol.clone();
        if let Ok(px) = rt.market.price(&fallback).await {
            let base = fallback.strip_suffix("USDT").unwrap_or(&fallback);
            out.push(LiveSignal {
                symbol: fallback.clone(),
                pair: format!("{base}/USDT"),
                direction: "BUY".into(),
                strength: 75,
                price: px,
                rsi: 50.0,
            });
        }
    }
    out
}
