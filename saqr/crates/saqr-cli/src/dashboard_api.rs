use axum::extract::{Path, Query, State};
use axum::response::IntoResponse;
use axum::Json;
use serde::Deserialize;
use serde_json::json;

use crate::control_actions;
use crate::runtime::SharedRuntime;

pub async fn binance_mirror(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    Json(rt.refresh_mirror().await)
}

pub async fn bot_toggle(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    Json(control_actions::toggle_bot(&rt).await)
}

pub async fn close_winners(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    let (code, body) = control_actions::close_winners(&rt).await;
    (code, Json(body))
}

pub async fn close_losers(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    let (code, body) = control_actions::close_losers(&rt).await;
    (code, Json(body))
}

pub async fn emergency_close_all(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    let (code, body) = control_actions::emergency_close_all(&rt).await;
    (code, Json(body))
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
    let (code, val) = control_actions::partial_close(
        &rt,
        &body.symbol,
        body.fraction.unwrap_or(0.5),
    )
    .await;
    (code, Json(val))
}

pub async fn close_one(
    State(rt): State<SharedRuntime>,
    Path(symbol): Path<String>,
) -> impl IntoResponse {
    let (code, val) = control_actions::partial_close(&rt, &symbol, 1.0).await;
    (code, Json(val))
}

#[derive(Deserialize)]
pub struct ReportQuery {
    pub period: Option<String>,
}

pub async fn report(
    State(rt): State<SharedRuntime>,
    Query(q): Query<ReportQuery>,
) -> impl IntoResponse {
    let period = q.period.as_deref().unwrap_or("daily");
    if rt.settings.is_paper_trading() {
        let r = rt.paper.report(period);
        let m = rt.refresh_mirror().await;
        return Json(json!({
            "period": period,
            "base_balance_usd": m.initial_balance_usd,
            "current_balance_usd": m.total_balance_usd,
            "winning_pnl_usd": m.winning_pnl_usd,
            "losing_pnl_usd": m.losing_pnl_usd,
            "open_positions": m.open_positions_count,
            "daily_profit_pct": m.daily_profit_pct,
            "win_amount_usd": r.get("win_amount_usd"),
            "loss_amount_usd": r.get("loss_amount_usd"),
            "win_count": r.get("win_count"),
            "loss_count": r.get("loss_count"),
            "execution": "paper",
        }));
    }
    let m = rt.refresh_mirror().await;
    Json(json!({
        "period": period,
        "base_balance_usd": m.initial_balance_usd,
        "current_balance_usd": m.total_balance_usd,
        "winning_pnl_usd": m.winning_pnl_usd,
        "losing_pnl_usd": m.losing_pnl_usd,
        "open_positions": m.open_positions_count,
        "daily_profit_pct": m.daily_profit_pct,
        "execution": "live",
    }))
}

#[derive(Deserialize)]
pub struct PaperEnterBody {
    pub symbol: String,
    #[serde(default = "default_risk_pct")]
    pub risk_pct: f64,
}

fn default_risk_pct() -> f64 {
    2.0
}

pub async fn paper_enter(
    State(rt): State<SharedRuntime>,
    Json(body): Json<PaperEnterBody>,
) -> impl IntoResponse {
    let (code, val) = control_actions::paper_enter(&rt, &body.symbol, body.risk_pct).await;
    (code, Json(val))
}

pub async fn trades_history(State(rt): State<SharedRuntime>) -> impl IntoResponse {
    if rt.settings.is_paper_trading() {
        let rows = rt.paper.history();
        return Json(json!({"ok": true, "trades": rows, "source": "paper"}));
    }
    let symbol = rt.settings.symbol.clone();
    match rt.binance.my_trades(&symbol, None).await {
        Ok(rows) => Json(json!({"ok": true, "trades": rows, "source": "binance"})),
        Err(e) => Json(json!({"ok": false, "error": e, "trades": []})),
    }
}
