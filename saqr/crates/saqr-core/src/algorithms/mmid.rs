/// MMID — Market Maker Intent Detection
pub struct MmidDetector;

impl MmidDetector {
    pub fn trap_score_scaled(cancel_rate_scaled: u32, modify_rate_scaled: u32) -> u32 {
        cancel_rate_scaled
            .saturating_add(modify_rate_scaled)
            .min(100_000_000)
    }
}
