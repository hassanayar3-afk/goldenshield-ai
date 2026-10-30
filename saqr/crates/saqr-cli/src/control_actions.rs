use axum::http::StatusCode;
use serde_json::{json, Value};

use saqr_core::binance::mirror::sell_qty_for_position;

use crate::bridge_sync;
use crate::runtime::SharedRuntime;
use crate::telegram_notify;

pub async fn toggle_bot(rt: &SharedRuntime) -> Value {
    let next = !rt.bot_is_running();
    rt.set_bot_running(next);
    telegram_notify::system_status(rt, next).await;
    json!({"ok": true, "bot_running": next})
}

pub async fn close_winners(rt: &SharedRuntime, source: &str) -> (StatusCode, Value) {
    execute_filter(rt, "close_winners", source, |pnl| *pnl > 0.0).await
}

pub async fn close_losers(rt: &SharedRuntime, source: &str) -> (StatusCode, Value) {
    execute_filter(rt, "close_losers", source, |pnl| *pnl < 0.0).await
}

pub async fn emergency_close_all(rt: &SharedRuntime, source: &str) -> (StatusCode, Value) {
    execute_filter(rt, "emergency_close_all", source, |_| true).await
}

/// Paper sandbox OR signed Binance Testnet/Live market entry (Telegram / signals / panel).
pub async fn paper_enter(
    rt: &SharedRuntime,
    symbol: &str,
    risk_pct: f64,
    source: &str,
) -> (StatusCode, Value) {
    enter_market(rt, symbol, risk_pct, source).await
}

pub async fn enter_market(
    rt: &SharedRuntime,
    symbol: &str,
    risk_pct: f64,
    source: &str,
) -> (StatusCode, Value) {
    let symbol = symbol.to_uppercase().replace('/', "");
    let risk = risk_pct.clamp(0.1, 5.0);

    if rt.settings.is_paper_trading() {
        let px = match rt.market.price(&symbol).await {
            Ok(p) => p,
            Err(e) => return (StatusCode::BAD_GATEWAY, json!({"ok": false, "error": e})),
        };
        let mirror = rt.refresh_mirror().await;
        let spend = mirror.total_balance_usd * (risk / 100.0);
        match rt.paper.market_buy(&symbol, spend, px) {
            Ok(qty) => {
                telegram_notify::paper_trade_entry(rt, &symbol, px, &format!("{qty:.8}"), spend)
                    .await;
                bridge_sync::sync_after_trade_action(rt, source, "paper_enter", 0).await;
                (
                    StatusCode::OK,
                    json!({"ok": true, "paper": true, "qty": qty, "price": px}),
                )
            }
            Err(e) => (StatusCode::BAD_REQUEST, json!({"ok": false, "error": e})),
        }
    } else {
        if !rt.settings.live_execution_enabled() {
            return (
                StatusCode::BAD_REQUEST,
                json!({"ok": false, "error": "trading_disabled"}),
            );
        }
        if !rt.binance.configured() {
            return (
                StatusCode::BAD_REQUEST,
                json!({"ok": false, "error": "binance_keys_missing"}),
            );
        }
        if let Err(e) = rt.binance.sync_time().await {
            tracing::warn!("binance time sync: {e}");
        }
        let _ = rt.binance.refresh_exchange_rules().await;
        let mirror = rt.refresh_mirror().await;
        let spend = mirror.usdt_free * (risk / 100.0);
        if spend < 5.0 {
            return (
                StatusCode::BAD_REQUEST,
                json!({"ok": false, "error": "insufficient_usdt_testnet", "usdt_free": mirror.usdt_free}),
            );
        }
        match rt.binance.market_buy_quote_usdt(&symbol, spend).await {
            Ok(order) => {
                let px = order
                    .price
                    .as_ref()
                    .and_then(|p| p.parse::<f64>().ok())
                    .or_else(|| {
                        order.cummulativeQuoteQty.as_ref().and_then(|q| {
                            q.parse::<f64>()
                                .ok()
                                .and_then(|quote| {
                                    order.executedQty.parse::<f64>().ok().map(|e| {
                                        quote / e.max(1e-12)
                                    })
                                })
                        })
                    })
                    .unwrap_or(0.0);
                telegram_notify::binance_trade_entry(
                    rt,
                    &symbol,
                    px,
                    &order.executedQty,
                    spend,
                    rt.settings.is_testnet_execution(),
                )
                .await;
                bridge_sync::sync_after_trade_action(rt, source, "binance_enter", 0).await;
                (
                    StatusCode::OK,
                    json!({
                        "ok": true,
                        "paper": false,
                        "testnet": rt.settings.binance.testnet,
                        "order": order,
                    }),
                )
            }
            Err(e) => (StatusCode::BAD_GATEWAY, json!({"ok": false, "error": e})),
        }
    }
}

pub async fn partial_close(
    rt: &SharedRuntime,
    symbol: &str,
    fraction: f64,
    source: &str,
) -> (StatusCode, Value) {
    let symbol = symbol.to_uppercase();
    let frac = fraction.clamp(0.05, 1.0);

    if rt.settings.is_paper_trading() {
        let px = match rt.market.price(&symbol).await {
            Ok(p) => p,
            Err(e) => {
                return (
                    StatusCode::BAD_GATEWAY,
                    json!({"ok": false, "error": e}),
                );
            }
        };
        match rt.paper.close_symbol(&symbol, frac, px) {
            Ok(pnl) => {
                if frac >= 0.99 {
                    rt.auto_entered_symbols.lock().remove(&symbol);
                }
                telegram_notify::paper_trade_exit(rt, &symbol, pnl, frac).await;
                bridge_sync::sync_after_trade_action(rt, source, "partial_close", 1).await;
                (StatusCode::OK, json!({"ok": true, "paper": true, "pnl_usd": pnl}))
            }
            Err(e) => (
                StatusCode::BAD_REQUEST,
                json!({"ok": false, "error": e}),
            ),
        }
    } else {
        let mirror = rt.refresh_mirror().await;
        let pos = mirror
            .positions
            .iter()
            .find(|p| p.symbol == symbol || p.id == symbol);
        let Some(pos) = pos else {
            return (
                StatusCode::NOT_FOUND,
                json!({"ok": false, "error": "position_not_found"}),
            );
        };
        let qty: f64 = pos.lot.parse().unwrap_or(0.0);
        let Some(qty_str) = sell_qty_for_position(&rt.binance, &pos.symbol, qty, frac) else {
            return (
                StatusCode::BAD_REQUEST,
                json!({"ok": false, "error": "qty_too_small"}),
            );
        };
        match rt
            .binance
            .market_order(&pos.symbol, "SELL", &qty_str)
            .await
        {
            Ok(order) => {
                telegram_notify::trade_exit(rt, pos, &order, frac).await;
                bridge_sync::sync_after_trade_action(rt, source, "partial_close", 1).await;
                (StatusCode::OK, json!({"ok": true, "order": order}))
            }
            Err(e) => (
                StatusCode::BAD_GATEWAY,
                json!({"ok": false, "error": e}),
            ),
        }
    }
}

pub async fn status_snapshot(rt: &SharedRuntime) -> Value {
    let m = rt.refresh_mirror().await;
    let px = rt
        .market
        .price(&rt.settings.symbol)
        .await
        .unwrap_or(0.0);
    json!({
        "ok": true,
        "mode": rt.settings.mode,
        "paper": rt.settings.is_paper_trading(),
        "bot_running": rt.bot_is_running(),
        "symbol": rt.settings.symbol,
        "market_price": px,
        "market_url": rt.settings.market_rest_url,
        "balance_usd": m.total_balance_usd,
        "daily_pct": m.daily_profit_pct,
        "open_positions": m.open_positions_count,
        "winning_pnl_usd": m.winning_pnl_usd,
        "losing_pnl_usd": m.losing_pnl_usd,
    })
}

async fn execute_filter<F>(
    rt: &SharedRuntime,
    action: &str,
    source: &str,
    pred: F,
) -> (StatusCode, Value)
where
    F: Fn(&f64) -> bool,
{
    if rt.settings.is_paper_trading() {
        let mirror = rt.refresh_mirror().await;
        let mut closed = 0_u32;
        for p in &mirror.positions {
            let px = match rt.market.price(&p.symbol).await {
                Ok(v) => v,
                Err(_) => continue,
            };
            let pnl = (px - p.entry) * p.lot.parse::<f64>().unwrap_or(0.0);
            if !pred(&pnl) {
                continue;
            }
            if let Ok(realized) = rt.paper.close_symbol(&p.symbol, 1.0, px) {
                closed += 1;
                rt.auto_entered_symbols.lock().remove(&p.symbol);
                telegram_notify::paper_trade_exit(rt, &p.symbol, realized, 1.0).await;
            }
        }
        bridge_sync::sync_after_trade_action(rt, source, action, closed).await;
        return (
            StatusCode::OK,
            json!({"ok": true, "closed": closed, "paper": true, "errors": []}),
        );
    }

    let mirror = rt.refresh_mirror().await;
    let mut closed = 0_u32;
    let mut errors: Vec<String> = Vec::new();
    for pos in &mirror.positions {
        if !pred(&pos.pnl) {
            continue;
        }
        let qty: f64 = pos.lot.parse().unwrap_or(0.0);
        let Some(qty_str) = sell_qty_for_position(&rt.binance, &pos.symbol, qty, 1.0) else {
            errors.push(format!("{}: qty_too_small", pos.symbol));
            continue;
        };
        match rt
            .binance
            .market_order(&pos.symbol, "SELL", &qty_str)
            .await
        {
            Ok(order) => {
                closed += 1;
                telegram_notify::trade_exit(rt, pos, &order, 1.0).await;
            }
            Err(e) => errors.push(format!("{}: {e}", pos.symbol)),
        }
    }
    bridge_sync::sync_after_trade_action(rt, source, action, closed).await;
    (
        StatusCode::OK,
        json!({
            "ok": errors.is_empty(),
            "closed": closed,
            "errors": errors,
        }),
    )
}
