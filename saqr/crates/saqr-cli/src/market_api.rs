use axum::extract::{Query, State};
use axum::Json;
use serde::Deserialize;
use serde_json::json;

use crate::market_signals;
use crate::runtime::SharedRuntime;

pub async fn liquidity(State(rt): State<SharedRuntime>) -> Json<serde_json::Value> {
    match rt.market.tickers_24h().await {
        Ok(all) => {
            let mut rows: Vec<serde_json::Value> = Vec::new();
            for sym in market_signals::watch_symbols(&rt) {
                if let Some(t) = all.iter().find(|x| x.symbol == sym) {
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

#[derive(Deserialize)]
pub struct TickerQuery {
    pub symbol: Option<String>,
}

pub async fn ticker(
    State(rt): State<SharedRuntime>,
    Query(q): Query<TickerQuery>,
) -> Json<serde_json::Value> {
    let sym = q
        .symbol
        .as_deref()
        .unwrap_or("BTCUSDT")
        .to_uppercase()
        .replace('/', "");
    match rt.market.price(&sym).await {
        Ok(price) => Json(json!({
            "ok": true,
            "symbol": sym,
            "price": price,
            "source": rt.market.base_url(),
        })),
        Err(e) => Json(json!({"ok": false, "symbol": sym, "error": e})),
    }
}

pub async fn signals(
    State(rt): State<SharedRuntime>,
    Query(q): Query<SignalQuery>,
) -> Json<serde_json::Value> {
    let interval = q.interval.as_deref().unwrap_or("15m");
    let rows = market_signals::fetch_live_signals(&rt, interval).await;
    let mut out = Vec::new();
    for (idx, s) in rows.iter().enumerate() {
        out.push(json!({
            "id": format!("{}-{idx}", s.symbol),
            "pair": s.pair,
            "symbol": s.symbol,
            "direction": s.direction,
            "strengthScore": s.strength,
            "timeframe": interval,
            "rsi": format!("{:.0}", s.rsi),
            "macd": if s.direction == "BUY" { "إيجابي" } else { "سلبي" },
            "executed": false,
            "price": s.price,
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
