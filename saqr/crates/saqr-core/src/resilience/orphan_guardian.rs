use std::collections::HashMap;
use parking_lot::RwLock;

/// حارس الأوامر اليتيمة — ClientOrderId محلي + مسار REST sweep
pub struct OrphanOrderGuardian {
    local_orders: RwLock<HashMap<String, u64>>,
}

impl OrphanOrderGuardian {
    pub fn new() -> Self {
        Self {
            local_orders: RwLock::new(HashMap::new()),
        }
    }

    pub fn register_local_order(&self, client_order_id: String, epoch: u64) {
        self.local_orders
            .write()
            .insert(client_order_id, epoch);
    }

    pub fn reconcile_with_exchange(&self, open_exchange_ids: &[String]) -> Vec<String> {
        let map = self.local_orders.read();
        let exchange_set: std::collections::HashSet<_> = open_exchange_ids.iter().collect();
        map.keys()
            .filter(|id| !exchange_set.contains(id))
            .cloned()
            .collect()
    }
}

impl Default for OrphanOrderGuardian {
    fn default() -> Self {
        Self::new()
    }
}
