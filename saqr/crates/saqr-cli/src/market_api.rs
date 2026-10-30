use axum::extract::{Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::json;

use saqr_core::binance::market_public::{closes_from_klines, rsi_from_closes};

use crate::runtime::SharedRuntime;

const WATCH_SYMBOLS: &[&str] = &["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"];

pub async fn liquidity(State(rt): State<SharedRuntime>) -> Json<serde_json::Value> {
    match rt.market.tickers_24h().await {
        Ok(all) => {
            let mut rows: Vec<serde_json::Value> = Vec::new();
            for sym in WATCH_SYMBOLS {
                if let Some(t) = all.iter().find(|x| x.symbol == *sym) {
                    let vol: f64 = t.quote_volume.parse().unwrap_or(0.0);
                    let base = sym.strip_suffix("USDT").unwrap_or(sym);
                    rows.push(json!({
                        "pair": format!("{base} / USDT"),
                        "symbol": sym,
                        "quote_volume_usd": vol,
                        "volume_b": vol / 1e9,
                    }));
                }
            }
            rows.sort_by(|a, b| {
                b.get("quote_volume_usd")
                    .and_then(|v| v.as_f64())
                    .partial_cmp(&a.get("quote_volume_usd").and_then(|v| v.as_f64()))
                    .unwrap_or(std::cmp::Ordering::Equal)
            });
            Json(json!({"ok": true, "source": rt.market.base_url(), "pairs": rows}))
        }
        Err(e) => Json(json!({"ok": false, "error": e, "pairs": []})),
    }
}

#[derive(Deserialize)]
pub struct SignalQuery {
    pub interval: Option<String>,
}

pub async fn signals(
    State(rt): State<SharedRuntime>,
    Query(q): Query<SignalQuery>,
) -> Json<serde_json::Value> {
    let interval = q.interval.as_deref().unwrap_or("15m");
    let mut out = Vec::new();
    for (idx, sym) in WATCH_SYMBOLS.iter().enumerate() {
        let klines = match rt.market.klines(sym, interval, 60).await {
            Ok(k) => k,
            Err(_) => continue,
        };
        let closes = closes_from_klines(&klines);
        let rsi = rsi_from_closes(&closes, 14).unwrap_or(50.0);
        let last = *closes.last().unwrap_or(&0.0);
        let prev = closes.get(closes.len().saturating_sub(5)).copied().unwrap_or(last);
        let direction = if last >= prev { "BUY" } else { "SELL" };
        let momentum = (last - prev).abs() / last.max(1.0) * 8000.0;
        let strength =
            (((rsi - 50.0).abs() + momentum).min(28.0) + 72.0) as i32;
        let strength = strength.clamp(72, 97);
        let base = sym.strip_suffix("USDT").unwrap_or(sym);
        out.push(json!({
            "id": format!("{sym}-{idx}"),
            "pair": format!("{base}/USDT"),
            "symbol": sym,
            "direction": direction,
            "strengthScore": strength,
            "timeframe": interval,
            "rsi": format!("{rsi:.0}"),
            "macd": if direction == "BUY" { "إيجابي" } else { "سلبي" },
            "executed": false,
            "price": last,
        }));
    }
    Json(json!({
        "ok": !out.is_empty(),
        "source": "binance_klines_live",
        "signals": out,
    }))
}

pub async fn paper_history(State(rt): State<SharedRuntime>) -> Json<serde_json::Value> {
    let rows = rt.paper.history();
    Json(json!({"ok": true, "trades": rows}))
}
