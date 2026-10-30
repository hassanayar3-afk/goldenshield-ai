use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use serde::Deserialize;
use serde_json::json;

use saqr_core::binance::mirror::sell_qty_for_position;

use crate::runtime::SharedRuntime;
use crate::telegram_notify;

pub async fn binance_mirror(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    let payload = rt.refresh_mirror().await;
    Json(payload)
}

pub async fn bot_toggle(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    let next = !rt.bot_is_running();
    rt.set_bot_running(next);
    let _ = telegram_notify::system_status(&rt, next).await;
    Json(json!({"ok": true, "bot_running": next}))
}

pub async fn close_winners(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    execute_filter(&rt, |pnl| *pnl > 0.0).await
}

pub async fn close_losers(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    execute_filter(&rt, |pnl| *pnl < 0.0).await
}

pub async fn emergency_close_all(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    execute_filter(&rt, |_| true).await
}

#[derive(Deserialize)]
pub struct PartialBody {
    pub symbol: String,
    pub fraction: Option<f64>,
}

pub async fn partial_close(
    State(rt): State<SharedRuntime>,
    Json(body): Json<PartialBody>,
) -> impl IntoResponse {
    do_partial_close(&rt, body).await
}

pub async fn close_one(
    State(rt): State<SharedRuntime>,
    Path(symbol): Path<String>,
) -> impl IntoResponse {
    do_partial_close(
        &rt,
        PartialBody {
            symbol,
            fraction: Some(1.0),
        },
    )
    .await
}

async fn do_partial_close(
    rt: &SharedRuntime,
    body: PartialBody,
) -> (StatusCode, Json<serde_json::Value>) {
    let mirror = rt.refresh_mirror().await;
    let pos = mirror
        .positions
        .iter()
        .find(|p| p.symbol == body.symbol || p.id == body.symbol);
    let Some(pos) = pos else {
        return (
            StatusCode::NOT_FOUND,
            Json(json!({"ok": false, "error": "position_not_found"})),
        );
    };
    let qty: f64 = pos.lot.parse().unwrap_or(0.0);
    let frac = body.fraction.unwrap_or(0.5).clamp(0.05, 1.0);
    let Some(qty_str) = sell_qty_for_position(&rt.binance, &pos.symbol, qty, frac) else {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({"ok": false, "error": "qty_too_small"})),
        );
    };
    match rt
        .binance
        .market_order(&pos.symbol, "SELL", &qty_str)
        .await
    {
        Ok(order) => {
            telegram_notify::trade_exit(rt, pos, &order, frac).await;
            (
                StatusCode::OK,
                Json(json!({"ok": true, "order": order})),
            )
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            Json(json!({"ok": false, "error": e})),
        ),
    }
}

pub async fn report(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    let m = rt.refresh_mirror().await;
    Json(json!({
        "period": "daily",
        "base_balance_usd": m.initial_balance_usd,
        "current_balance_usd": m.total_balance_usd,
        "winning_pnl_usd": m.winning_pnl_usd,
        "losing_pnl_usd": m.losing_pnl_usd,
        "open_positions": m.open_positions_count,
        "daily_profit_pct": m.daily_profit_pct,
    }))
}

pub async fn trades_history(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    let symbol = rt.settings.symbol.clone();
    match rt.binance.my_trades(&symbol, None).await {
        Ok(rows) => Json(json!({"ok": true, "trades": rows})),
        Err(e) => Json(json!({"ok": false, "error": e, "trades": []})),
    }
}

async fn execute_filter<F>(rt: &SharedRuntime, pred: F) -> (StatusCode, Json<serde_json::Value>)
where
    F: Fn(&f64) -> bool,
{
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
    (
        StatusCode::OK,
        Json(json!({
            "ok": errors.is_empty(),
            "closed": closed,
            "errors": errors,
        })),
    )
}
