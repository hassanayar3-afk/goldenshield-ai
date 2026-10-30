/// HIRA — Hidden Liquidity Reconstruction Algorithm
pub struct HiraEngine;

impl HiraEngine {
    pub fn estimate_hidden_size_scaled(
        visible_depth_scaled: i64,
        micro_fill_probability_scaled: u32,
    ) -> i64 {
        let boost = (visible_depth_scaled as i128 * micro_fill_probability_scaled as i128)
            / 100_000_000;
        boost.clamp(0, i64::MAX as i128) as i64
    }
}
