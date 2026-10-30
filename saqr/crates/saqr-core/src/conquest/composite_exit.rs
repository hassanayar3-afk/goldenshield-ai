/// Directive 2 — L2/CVD Composite Exit (+3%..+7%)
pub struct CompositeExitEngine;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExitSignal {
    Hold,
    SecureLoot,
    StopLoss,
}

impl CompositeExitEngine {
    pub fn evaluate(
        l2_imbalance: f64,
        cvd_slope: f64,
        pnl_pct: f64,
    ) -> ExitSignal {
        if pnl_pct >= 3.0 && pnl_pct <= 7.0 {
            return ExitSignal::SecureLoot;
        }
        if l2_imbalance < 0.35 && cvd_slope < 0.0 {
            return ExitSignal::StopLoss;
        }
        ExitSignal::Hold
    }
}
