mod control_actions;
mod dashboard_api;
mod env_loader;
mod market_api;
mod gc_worker;
mod hot_loop;
mod integrations_bridge;
mod runtime;
mod telegram_bridge;
mod telegram_notify;
mod web_server;

use std::path::PathBuf;
use std::sync::Arc;

use saqr_core::config::env_settings::SaqrSettings;
use saqr_core::orchestrator::decision_cascade::DecisionCascade;
use saqr_core::orchestrator::phase4_master_orchestrator::Phase4MasterOrchestrator;
use saqr_core::orchestrator::sovereign_matrix::{SovereignMatrix, SovereignMatrixInputs};
use tokio::sync::mpsc;

use runtime::SharedRuntime;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--version" || a == "-V") {
        println!("SAQR Engine v6.2.3");
        return Ok(());
    }

    env_loader::load_env_files();
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let settings = SaqrSettings::from_env();

    if args.iter().any(|a| a == "--check") {
        let ok = run_check(&settings);
        if !ok {
            std::process::exit(1);
        }
        return Ok(());
    }

    let rt = Arc::new(SharedRuntime::new(settings.clone()));
    let (gc_tx, gc_rx) = mpsc::channel(1024);
    tokio::spawn(gc_worker::run_gc_worker(gc_rx));

    let orchestrator = Phase4MasterOrchestrator::new(settings.initial_balance_usd);
    let cascade = DecisionCascade::new();
    orchestrator.heartbeat();

    let level0 = cascade.level0_macro(0, true);
    tracing::info!("Decision cascade level0: {:?}", level0);

    let matrix_ok = SovereignMatrix::commander_may_fire(SovereignMatrixInputs {
        is_execution_safe: settings.enable_trading,
        macro_risk_score: 0.05,
        momentum_consensus: 90.0,
        sovereign_score: 92.0,
    });
    tracing::info!(
        "Sovereign matrix pass={matrix_ok} mode={} trading={}",
        settings.mode,
        settings.enable_trading
    );

    if settings.is_paper_trading() {
        tracing::info!(
            "Paper mode — live market {} · sandbox capital {:.2} USD",
            settings.market_rest_url,
            settings.initial_balance_usd
        );
    } else if settings.require_integrated_demo {
        tracing::info!("SAQR_REQUIRE_INTEGRATED_DEMO=true — Testnet execution path");
    }

    integrations_bridge::spawn_integrations_bridge(settings.clone());
    telegram_bridge::spawn_bidirectional_bridge(Arc::clone(&rt));
    hot_loop::spawn_hot_loop(Arc::clone(&rt));
    spawn_console_live_ticker(Arc::clone(&rt));

    let web_root = resolve_web_root();
    let web_rt = (*rt).clone();
    tokio::spawn(async move {
        if let Err(e) = web_server::start_web(web_rt, &web_root).await {
            tracing::error!("web server error: {e}");
        }
    });

    let _ = gc_tx.send(0).await;
    orchestrator.heartbeat();

    tracing::info!("صقر SAQR Engine v6.2.3 — hot loop + dashboard linked to .env");

    tokio::signal::ctrl_c().await?;
    Ok(())
}

fn run_check(settings: &SaqrSettings) -> bool {
    let mut ok = true;
    println!("SAQR --check v6.2.3");
    println!("  mode: {}", settings.mode);
    println!("  SAQR_ENABLE_TRADING: {}", settings.enable_trading);
    println!("  paper_trading: {}", settings.is_paper_trading());
    println!("  market_rest: {}", settings.market_rest_url);
    println!("  binance_rest: {}", settings.binance.rest_base_url);
    println!("  symbol: {}", settings.symbol);
    println!("  initial_balance_usd: {}", settings.initial_balance_usd);
    println!("  web bind: {}:{}", settings.web_bind_host, settings.web_bind_port);
    if settings.api_key.is_empty() {
        println!("  BINANCE_API_KEY: MISSING");
        ok = false;
    } else {
        println!("  BINANCE_API_KEY: set");
    }
    if settings.api_secret.is_empty() {
        println!("  BINANCE_API_SECRET: MISSING");
        ok = false;
    } else {
        println!("  BINANCE_API_SECRET: set");
    }
    if settings.telegram.bot_token.is_empty() || settings.telegram.bot_token.len() < 40 {
        println!("  TELEGRAM_BOT_TOKEN: MISSING or truncated");
        ok = false;
    } else {
        println!("  TELEGRAM_BOT_TOKEN: set");
    }
    if settings.telegram.chat_id.is_empty() {
        println!("  TELEGRAM_CHAT_ID: MISSING");
        ok = false;
    } else {
        println!("  TELEGRAM_CHAT_ID: set");
    }
    println!("  SAQR_TELEGRAM_BRIDGE: {}", settings.telegram_bridge_enabled);
    if !settings.is_paper_trading() {
        println!("  [warn] not in paper mode");
    }
    if ok {
        println!("  preflight: OK");
    } else {
        println!("  preflight: FAILED");
    }
    ok
}

/// طبقة عرض: سطر حي في نافذة CMD كل ~5 ث (BTC + رصيد Paper).
fn spawn_console_live_ticker(rt: Arc<SharedRuntime>) {
    tokio::spawn(async move {
        let mut tick = tokio::time::interval(std::time::Duration::from_secs(5));
        tick.tick().await;
        loop {
            tick.tick().await;
            let sym = rt.settings.symbol.clone();
            let px = rt.market.price(&sym).await.unwrap_or(0.0);
            let m = rt.refresh_mirror().await;
            let bot = if rt.bot_is_running() { "ON" } else { "OFF" };
            println!(
                "[SAQR LIVE] {sym} {px:.2} | balance {:.2} USD | open {} | bot {bot}",
                m.total_balance_usd,
                m.open_positions_count
            );
        }
    });
}

fn resolve_web_root() -> String {
    let candidates = [
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../web/control_terminal"),
        PathBuf::from("/home/ubuntu/saqr/web/control_terminal"),
        PathBuf::from("web/control_terminal"),
    ];
    for p in candidates {
        if p.join("index.html").is_file() {
            return p.to_string_lossy().into_owned();
        }
    }
    "web/control_terminal".into()
}
