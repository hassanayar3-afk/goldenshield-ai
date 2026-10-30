use std::sync::atomic::{AtomicI64, AtomicU64, Ordering};
use std::sync::Arc;

use tokio::sync::mpsc;

use super::battle_status::BattleStatus;
use super::local_weight_bucket::LocalWeightBucket;
use super::selected_battalion::SelectedBattalion;

pub struct SovereignConquestEngine {
    pub battle_status: Arc<AtomicU64>,
    pub account_balance_scaled: AtomicI64,
    pub current_target: Option<SelectedBattalion>,
    pub weight_bucket: Arc<LocalWeightBucket>,
    last_telegram_dispatch_ms: Arc<AtomicU64>,
    signals_suppressed_count: Arc<AtomicU64>,
    gc_trigger_tx: mpsc::Sender<u64>,
}

impl SovereignConquestEngine {
    pub fn new(initial_balance_usd: f64, gc_tx: mpsc::Sender<u64>) -> Self {
        Self {
            battle_status: Arc::new(AtomicU64::new(BattleStatus::ScoutPhase as u64)),
            account_balance_scaled: AtomicI64::new(
                (initial_balance_usd * 100_000_000.0) as i64,
            ),
            current_target: None,
            weight_bucket: Arc::new(LocalWeightBucket::new()),
            last_telegram_dispatch_ms: Arc::new(AtomicU64::new(0)),
            signals_suppressed_count: Arc::new(AtomicU64::new(0)),
            gc_trigger_tx: gc_tx,
        }
    }

    pub fn calculate_dynamic_kelly_position_size(&self, battalion: &SelectedBattalion) -> f64 {
        let p = battalion.win_rate_historical.clamp(0.55, 0.85);
        let b = battalion.win_loss_ratio.clamp(1.2, 3.0);
        let q = 1.0 - p;
        let raw_kelly = (b * p - q) / b;
        let fractional_kelly = raw_kelly * 0.30;
        let volatility_scalar = (0.015 / battalion.atr_volatility.max(0.003)).clamp(0.4, 1.2);
        let calculated_size = fractional_kelly * volatility_scalar;
        calculated_size.clamp(0.01, 0.03)
    }

    pub fn select_prime_battalion(
        &mut self,
        candidates: Vec<SelectedBattalion>,
    ) -> Option<(SelectedBattalion, f64)> {
        if !self.weight_bucket.can_send_request(5) {
            return None;
        }

        let mut sorted_candidates = candidates;
        sorted_candidates.sort_by(|a, b| {
            let score_a = if a.consensus_score.is_nan() || a.volume_acceleration.is_nan() {
                0.0
            } else {
                a.consensus_score * a.volume_acceleration
            };
            let score_b = if b.consensus_score.is_nan() || b.volume_acceleration.is_nan() {
                0.0
            } else {
                b.consensus_score * b.volume_acceleration
            };
            score_b
                .partial_cmp(&score_a)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let prime = sorted_candidates.into_iter().next()?;
        if prime.consensus_score < 90.0 {
            let _ = self.gc_trigger_tx.try_send(1);
            return None;
        }

        let size = self.calculate_dynamic_kelly_position_size(&prime);
        self.current_target = Some(prime.clone());
        self.battle_status
            .store(BattleStatus::Engaging as u64, Ordering::Release);
        Some((prime, size))
    }

    pub fn should_dispatch_telegram(&self, now_ms: u64, is_critical: bool) -> bool {
        if is_critical {
            return true;
        }
        let last = self.last_telegram_dispatch_ms.load(Ordering::Acquire);
        if now_ms.saturating_sub(last) >= 900_000 {
            self.last_telegram_dispatch_ms
                .store(now_ms, Ordering::Release);
            return true;
        }
        self.signals_suppressed_count
            .fetch_add(1, Ordering::Relaxed);
        false
    }
}
