use std::sync::atomic::{AtomicU64, Ordering};

pub struct StreamFreezeWatchdog {
    last_tick_timestamp_ms: AtomicU64,
    max_allowed_freeze_ms: u64,
}

impl StreamFreezeWatchdog {
    pub fn new(max_allowed_freeze_ms: u64) -> Self {
        Self {
            last_tick_timestamp_ms: AtomicU64::new(0),
            max_allowed_freeze_ms,
        }
    }

    pub fn on_tick_received(&self, current_time_ms: u64) {
        self.last_tick_timestamp_ms
            .store(current_time_ms, Ordering::Release);
    }

    pub fn is_stream_frozen(&self, current_time_ms: u64) -> bool {
        let last = self.last_tick_timestamp_ms.load(Ordering::Acquire);
        if last == 0 {
            return false;
        }
        (current_time_ms.saturating_sub(last)) > self.max_allowed_freeze_ms
    }
}
