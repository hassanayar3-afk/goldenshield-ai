use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// غلاف مستقل لقاطع التيار — لا يدمج مع حالة السوق.
pub struct EmergencyLockout {
    halt: Arc<AtomicBool>,
}

impl EmergencyLockout {
    pub fn new(halt: Arc<AtomicBool>) -> Self {
        Self { halt }
    }

    pub fn engage(&self) {
        self.halt.store(true, Ordering::SeqCst);
    }

    pub fn is_engaged(&self) -> bool {
        self.halt.load(Ordering::Acquire)
    }
}
