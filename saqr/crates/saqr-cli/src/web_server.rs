use std::net::SocketAddr;

use axum::routing::{get, post};
use axum::Router;
use tower_http::cors::CorsLayer;
use tower_http::services::ServeDir;

use crate::dashboard_api;
use crate::market_api;
use crate::runtime::SharedRuntime;

pub async fn start_web(rt: SharedRuntime, web_root: &str) -> Result<(), std::io::Error> {
    let settings = rt.settings.clone();
    let app = Router::new()
        .route("/api/health", get(health))
        .route("/api/status", get(status))
        .route("/api/binance_mirror", get(dashboard_api::binance_mirror))
        .route("/api/report", get(dashboard_api::report))
        .route("/api/trades/history", get(dashboard_api::trades_history))
        .route("/api/market/liquidity", get(market_api::liquidity))
        .route("/api/market/signals", get(market_api::signals))
        .route("/api/paper/enter", post(dashboard_api::paper_enter))
        .route("/api/control/bot_toggle", post(dashboard_api::bot_toggle))
        .route("/api/control/close_winners", post(dashboard_api::close_winners))
        .route("/api/control/close_losers", post(dashboard_api::close_losers))
        .route("/api/control/emergency_close", post(dashboard_api::emergency_close_all))
        .route("/api/control/partial_close", post(dashboard_api::partial_close))
        .route("/api/control/close/:symbol", post(dashboard_api::close_one))
        .nest_service("/", ServeDir::new(web_root))
        .layer(CorsLayer::permissive())
        .with_state(rt);

    let addr: SocketAddr = format!("{}:{}", settings.web_bind_host, settings.web_bind_port)
        .parse()
        .unwrap_or_else(|_| "127.0.0.1:8788".parse().unwrap());
    let listener = match tokio::net::TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) if e.kind() == std::io::ErrorKind::AddrInUse => {
            tracing::error!(
                "\n╔══════════════════════════════════════════════════════╗\n║  Web port {} in use (Windows 10048). Set SAQR_WEB_BIND_PORT=8789 in .env  ║\n╚══════════════════════════════════════════════════════╝",
                settings.web_bind_port
            );
            return Err(e);
        }
        Err(e) => return Err(e),
    };
    tracing::info!("SAQR Control Terminal v6.2.3 on http://{addr}");
    axum::serve(listener, app).await
}

async fn health() -> axum::Json<serde_json::Value> {
    axum::Json(serde_json::json!({"ok": true, "engine": "SAQR v6.2.3"}))
}

async fn status(
    axum::extract::State(rt): axum::extract::State<SharedRuntime>,
) -> axum::Json<serde_json::Value> {
    let s = &rt.settings;
    axum::Json(serde_json::json!({
        "mode": s.mode,
        "symbol": s.symbol,
        "enable_trading": s.enable_trading,
        "paper_trading": s.is_paper_trading(),
        "market_rest_url": s.market_rest_url,
        "require_integrated_demo": s.require_integrated_demo,
        "binance_testnet": s.binance.testnet,
        "binance_rest_url": s.binance.rest_base_url,
        "binance_configured": rt.binance.configured(),
        "telegram_configured": rt.telegram.is_configured(),
        "web_port": s.web_bind_port,
        "bot_running": rt.bot_is_running(),
    }))
}
