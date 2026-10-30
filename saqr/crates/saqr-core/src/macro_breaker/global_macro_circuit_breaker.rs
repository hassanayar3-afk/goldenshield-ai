use std::sync::atomic::{AtomicBool, Ordering};

pub struct GlobalMacroCircuitBreaker {
    is_emergency_halt: AtomicBool,
    btc_drop_threshold_scaled: i64,
}

impl GlobalMacroCircuitBreaker {
    pub fn new() -> Self {
        Self {
            is_emergency_halt: AtomicBool::new(false),
            btc_drop_threshold_scaled: 1_500_000,
        }
    }

    pub fn check_btc_shock_and_halt(&self, btc_price_change_3s_scaled: i64) -> bool {
        if btc_price_change_3s_scaled <= -self.btc_drop_threshold_scaled {
            self.is_emergency_halt.store(true, Ordering::SeqCst);
            return true;
        }
        false
    }

    pub fn is_halted(&self) -> bool {
        self.is_emergency_halt.load(Ordering::Acquire)
    }
}

impl Default for GlobalMacroCircuitBreaker {
    fn default() -> Self {
        Self::new()
    }
}
