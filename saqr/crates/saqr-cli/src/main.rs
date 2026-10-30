mod dashboard_api;
mod env_loader;
mod market_api;
mod gc_worker;
mod hot_loop;
mod integrations_bridge;
mod runtime;
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
        run_check(&settings);
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
    hot_loop::spawn_hot_loop(Arc::clone(&rt));

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

fn run_check(settings: &SaqrSettings) {
    println!("SAQR --check v6.2.3");
    println!("  mode: {}", settings.mode);
    println!("  SAQR_ENABLE_TRADING: {}", settings.enable_trading);
    println!("  paper_trading: {}", settings.is_paper_trading());
    println!("  market_rest: {}", settings.market_rest_url);
    println!("  web bind: {}:{}", settings.web_bind_host, settings.web_bind_port);
    println!(
        "  BINANCE_API_KEY: {}",
        if settings.api_key.is_empty() {
            "MISSING"
        } else {
            "set"
        }
    );
    println!(
        "  TELEGRAM_BOT_TOKEN: {}",
        if settings.telegram.bot_token.is_empty() {
            "MISSING"
        } else {
            "set"
        }
    );
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
