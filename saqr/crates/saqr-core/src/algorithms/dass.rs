/// DASS — Dynamic Adverse Selection Shield
pub struct DassShield;

impl DassShield {
    pub fn widen_margin_bps(base_bps: u32, toxicity_scaled: u32) -> u32 {
        base_bps.saturating_add(toxicity_scaled / 1_000_000)
    }
}
