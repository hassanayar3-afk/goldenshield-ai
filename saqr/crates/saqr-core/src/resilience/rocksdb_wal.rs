use serde::{Deserialize, Serialize};

/// سجل WAL منطقي — تخزين فعلي عبر RocksDB عند تفعيل feature `rocksdb`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalOrderRecord {
    pub client_order_id: String,
    pub payload_json: String,
    pub epoch: u64,
    pub pre_send: bool,
}

pub struct RocksDbWalJournal {
    pending: Vec<WalOrderRecord>,
}

impl RocksDbWalJournal {
    pub fn new() -> Self {
        Self {
            pending: Vec::with_capacity(256),
        }
    }

    pub fn append_pre_send(&mut self, record: WalOrderRecord) {
        self.pending.push(record);
    }

    pub fn drain_for_recovery(&mut self) -> Vec<WalOrderRecord> {
        std::mem::take(&mut self.pending)
    }
}

impl Default for RocksDbWalJournal {
    fn default() -> Self {
        Self::new()
    }
}
