/// بروتوكول المعايرة الزمنية والتطهير السيادي (Stale State Purge)
pub struct TemporalReconciliation {
    max_stale_ms: u64,
}

impl TemporalReconciliation {
    pub fn new(max_stale_minutes: u64) -> Self {
        Self {
            max_stale_ms: max_stale_minutes * 60 * 1000,
        }
    }

    pub fn must_purge_state(&self, last_state_ts_ms: u64, exchange_now_ms: u64) -> bool {
        exchange_now_ms.saturating_sub(last_state_ts_ms) > self.max_stale_ms
    }
}

impl Default for TemporalReconciliation {
    fn default() -> Self {
        Self::new(30)
    }
}
