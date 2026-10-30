use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

/// بنية حالة السوق الموحدة والآمنة لتفادي أخطاء التزامن (Zero-Copy Layout)
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct UnifiedMarketState {
    pub symbol_hash: u64,
    pub timestamp_mono_ns: u64,
    pub adjusted_price_scaled: i64,
    pub cvd_h1_scaled: i64,
    pub consensus_score_scaled: u32,
    pub lock_status: u8,
}

impl UnifiedMarketState {
    #[inline(always)]
    pub fn is_safe_to_execute(&self) -> bool {
        self.lock_status == 0
    }
}

/// قاطع التيار الذري الفوري (Emergency Lockout)
pub struct AtomicEmergencyLock {
    frozen: AtomicBool,
    silent_disconnect_ms: AtomicU64,
}

impl AtomicEmergencyLock {
    pub fn new() -> Self {
        Self {
            frozen: AtomicBool::new(false),
            silent_disconnect_ms: AtomicU64::new(0),
        }
    }

    pub fn trip(&self) {
        self.frozen.store(true, Ordering::SeqCst);
    }

    pub fn is_locked(&self) -> bool {
        self.frozen.load(Ordering::SeqCst)
    }

    pub fn record_silent_ms(&self, ms: u64) {
        self.silent_disconnect_ms.store(ms, Ordering::Release);
        if ms > 1500 {
            self.trip();
        }
    }
}

impl Default for AtomicEmergencyLock {
    fn default() -> Self {
        Self::new()
    }
}

/// Fixed-Point Scale 10^8 — مرجع مشترك
pub const SCALE_8: i64 = 100_000_000;
