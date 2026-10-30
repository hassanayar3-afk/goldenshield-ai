use std::sync::atomic::{AtomicU64, Ordering};

/// Exponential Backoff & Flood-Wait Mitigation
pub struct TelegramAntiFlood {
    backoff_ms: AtomicU64,
    last_error_ms: AtomicU64,
}

impl TelegramAntiFlood {
    pub fn new() -> Self {
        Self {
            backoff_ms: AtomicU64::new(1000),
            last_error_ms: AtomicU64::new(0),
        }
    }

    pub fn on_rate_limited(&self, now_ms: u64) {
        let current = self.backoff_ms.load(Ordering::Acquire);
        let next = (current * 2).min(300_000);
        self.backoff_ms.store(next, Ordering::Release);
        self.last_error_ms.store(now_ms, Ordering::Release);
    }

    pub fn wait_ms(&self) -> u64 {
        self.backoff_ms.load(Ordering::Acquire)
    }

    pub fn reset_on_success(&self) {
        self.backoff_ms.store(1000, Ordering::Release);
    }
}

impl Default for TelegramAntiFlood {
    fn default() -> Self {
        Self::new()
    }
}
