use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

pub struct LocalWeightBucket {
    pub current_weight: AtomicU64,
    pub last_reset_timestamp_ms: AtomicU64,
}

impl LocalWeightBucket {
    pub fn new() -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        Self {
            current_weight: AtomicU64::new(0),
            last_reset_timestamp_ms: AtomicU64::new(now),
        }
    }

    #[inline(always)]
    pub fn can_send_request(&self, request_weight: u64) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        let last_reset = self.last_reset_timestamp_ms.load(Ordering::Acquire);

        if now.saturating_sub(last_reset) >= 60_000 {
            self.current_weight.store(0, Ordering::Release);
            self.last_reset_timestamp_ms.store(now, Ordering::Release);
        }

        let current = self.current_weight.load(Ordering::Acquire);
        if current + request_weight > 4000 {
            return false;
        }
        self.current_weight
            .fetch_add(request_weight, Ordering::SeqCst);
        true
    }
}

impl Default for LocalWeightBucket {
    fn default() -> Self {
        Self::new()
    }
}
