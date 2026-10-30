use std::sync::atomic::{AtomicU64, Ordering};

/// قفل الحالة الذري عبر Epoch Versioning (RocksDB split-brain guard)
pub struct EpochStateLock {
    epoch: AtomicU64,
}

impl EpochStateLock {
    pub fn new() -> Self {
        Self {
            epoch: AtomicU64::new(0),
        }
    }

    pub fn bump_epoch(&self) -> u64 {
        self.epoch.fetch_add(1, Ordering::SeqCst) + 1
    }

    pub fn current(&self) -> u64 {
        self.epoch.load(Ordering::Acquire)
    }

    pub fn validate(&self, expected: u64) -> bool {
        self.current() == expected
    }
}

impl Default for EpochStateLock {
    fn default() -> Self {
        Self::new()
    }
}
