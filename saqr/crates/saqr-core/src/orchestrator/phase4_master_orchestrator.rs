use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::Arc;

use crate::core::emergency_lockout::EmergencyLockout;
use crate::core::unified_market_state::UnifiedMarketState;
use crate::resilience::compounding_growth::CompoundingGrowth;
use crate::resilience::rocksdb_wal::RocksDbWalJournal;
use crate::resilience::watchdog::ProcessWatchdog;

/// Phase 4 Master Orchestrator — تجميد ذري + WAL + compounding
pub struct Phase4MasterOrchestrator {
    emergency: Arc<AtomicBool>,
    lockout: EmergencyLockout,
    wal: RocksDbWalJournal,
    compounding: CompoundingGrowth,
    watchdog: ProcessWatchdog,
    time_offset: Arc<AtomicI64>,
}

impl Phase4MasterOrchestrator {
    pub fn new(initial_balance_usd: f64) -> Self {
        let emergency = Arc::new(AtomicBool::new(false));
        Self {
            lockout: EmergencyLockout::new(emergency.clone()),
            emergency,
            wal: RocksDbWalJournal::new(),
            compounding: CompoundingGrowth::new(initial_balance_usd, 10),
            watchdog: ProcessWatchdog::new(),
            time_offset: Arc::new(AtomicI64::new(0)),
        }
    }

    pub fn time_offset(&self) -> Arc<AtomicI64> {
        self.time_offset.clone()
    }

    pub fn heartbeat(&self) {
        self.watchdog.heartbeat();
    }

    pub fn needs_restart(&self) -> bool {
        self.watchdog.needs_hot_restart()
    }

    pub fn may_execute(&self, state: &UnifiedMarketState) -> bool {
        !self.lockout.is_engaged() && state.is_safe_to_execute()
    }

    pub fn trip_emergency(&self) {
        self.lockout.engage();
    }

    pub fn wal_mut(&mut self) -> &mut RocksDbWalJournal {
        &mut self.wal
    }

    pub fn apply_daily_compound(&mut self, pnl_scaled: i128) {
        self.compounding.apply_daily_compound(pnl_scaled);
    }

    pub fn silent_disconnect_trip(&self, silent_ms: u64) {
        if silent_ms > 1500 {
            self.emergency.store(true, Ordering::SeqCst);
        }
    }
}
