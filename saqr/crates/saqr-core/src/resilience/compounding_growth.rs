use crate::core::unified_market_state::SCALE_8;

/// إدارة الحساب التراكمي — تحديث مرجع 24h مع خصم رسوم تقريبي
pub struct CompoundingGrowth {
    reference_balance_scaled: u128,
    fee_rate_scaled: u128,
}

impl CompoundingGrowth {
    pub fn new(initial_usd: f64, fee_bps: u32) -> Self {
        let balance = (initial_usd * SCALE_8 as f64) as u128;
        let fee = (fee_bps as u128) * (SCALE_8 as u128) / 10_000;
        Self {
            reference_balance_scaled: balance,
            fee_rate_scaled: fee,
        }
    }

    pub fn apply_daily_compound(&mut self, pnl_scaled: i128) {
        let gross = self.reference_balance_scaled as i128 + pnl_scaled;
        let fee = (gross.max(0) as u128 * self.fee_rate_scaled) / (SCALE_8 as u128);
        self.reference_balance_scaled = (gross.max(0) as u128).saturating_sub(fee);
    }

    pub fn reference_balance_scaled(&self) -> u128 {
        self.reference_balance_scaled
    }
}
