//! SAQR Engine v6.0 — نواة Rust (ملف واحد = اختصاص واحد).

pub mod algorithms;
pub mod binance;
pub mod config;
pub mod conquest;
pub mod core;
pub mod ipc;
pub mod liquidity;
pub mod macro_breaker;
pub mod momentum;
pub mod orchestrator;
pub mod resilience;
pub mod routing;
pub mod telegram;
pub mod time;

pub use orchestrator::decision_cascade::DecisionCascade;
pub use orchestrator::phase4_master_orchestrator::Phase4MasterOrchestrator;
