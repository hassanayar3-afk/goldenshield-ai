use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

/// Watchdog — Heartbeat Timeout > 500ms
pub struct ProcessWatchdog {
    last_heartbeat_ms: AtomicU64,
    max_gap_ms: u64,
}

impl ProcessWatchdog {
    pub fn new() -> Self {
        Self {
            last_heartbeat_ms: AtomicU64::new(0),
            max_gap_ms: 500,
        }
    }

    pub fn heartbeat(&self) {
        let now = SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        self.last_heartbeat_ms.store(now, Ordering::Release);
    }

    pub fn needs_hot_restart(&self) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        let last = self.last_heartbeat_ms.load(Ordering::Acquire);
        if last == 0 {
            return false;
        }
        now.saturating_sub(last) > self.max_gap_ms
    }
}

impl Default for ProcessWatchdog {
    fn default() -> Self {
        Self::new()
    }
}
