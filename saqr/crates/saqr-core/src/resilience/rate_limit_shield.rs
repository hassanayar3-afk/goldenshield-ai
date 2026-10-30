use std::sync::atomic::{AtomicU64, Ordering};

/// Pre-emptive Rate Limiter — سقف 70% من 1200 weight/min ≈ 840
pub struct RateLimitShield {
    weight_used: AtomicU64,
    window_start_ms: AtomicU64,
    max_weight_per_minute: u64,
}

impl RateLimitShield {
    pub fn new() -> Self {
        Self {
            weight_used: AtomicU64::new(0),
            window_start_ms: AtomicU64::new(0),
            max_weight_per_minute: 840,
        }
    }

    pub fn allow(&self, weight: u64, now_ms: u64) -> bool {
        let start = self.window_start_ms.load(Ordering::Acquire);
        if start == 0 || now_ms.saturating_sub(start) >= 60_000 {
            self.weight_used.store(0, Ordering::Release);
            self.window_start_ms.store(now_ms, Ordering::Release);
        }
        let used = self.weight_used.load(Ordering::Acquire);
        if used + weight > self.max_weight_per_minute {
            return false;
        }
        self.weight_used.fetch_add(weight, Ordering::SeqCst);
        true
    }
}

impl Default for RateLimitShield {
    fn default() -> Self {
        Self::new()
    }
}
