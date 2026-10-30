use std::sync::atomic::AtomicI64;
use std::sync::Arc;

use crate::time::chrono_guard::ChronoGuard;

pub struct BinanceTimeSync {
    guard: ChronoGuard,
}

impl BinanceTimeSync {
    pub fn new(offset: Arc<AtomicI64>) -> Self {
        Self {
            guard: ChronoGuard::new(offset),
        }
    }

    pub fn apply_server_time_ms(&self, server_ms: u64) {
        self.guard.update_offset(server_ms);
    }

    pub fn guard(&self) -> &ChronoGuard {
        &self.guard
    }
}
