pub struct ApexEmperorCore {
    consensus_threshold_scaled: u32,
}

impl ApexEmperorCore {
    pub fn new() -> Self {
        Self {
            consensus_threshold_scaled: 85_000_000,
        }
    }

    pub fn calculate_real_flow_scaled(
        trade_volume_scaled: i64,
        aggression_factor_scaled: i64,
        spoofing_delta_scaled: i64,
    ) -> i64 {
        let raw_flow = (trade_volume_scaled * aggression_factor_scaled) / 100_000_000;
        raw_flow.saturating_sub(spoofing_delta_scaled)
    }

    pub fn evaluate_consensus(
        &self,
        real_flow_scaled: i64,
        micro_acceleration_scaled: i64,
        volatility_factor_scaled: u32,
    ) -> bool {
        if volatility_factor_scaled > 150_000_000 {
            return false;
        }
        let score_scaled =
            (real_flow_scaled.abs() + micro_acceleration_scaled.abs()) as u32;
        score_scaled >= self.consensus_threshold_scaled
    }
}

impl Default for ApexEmperorCore {
    fn default() -> Self {
        Self::new()
    }
}
