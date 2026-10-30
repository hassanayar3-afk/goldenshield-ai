/// مصفوفة توحيد القواعد v9.0 — شروط التمرير بين الأقسام الأربعة
#[derive(Debug, Clone, Copy)]
pub struct SovereignMatrixInputs {
    pub is_execution_safe: bool,
    pub macro_risk_score: f64,
    pub momentum_consensus: f64,
    pub sovereign_score: f64,
}

pub struct SovereignMatrix;

impl SovereignMatrix {
    pub fn commander_may_fire(i: SovereignMatrixInputs) -> bool {
        i.is_execution_safe
            && i.macro_risk_score < 0.20
            && i.momentum_consensus >= 85.0
            && i.sovereign_score >= 90.0
    }
}
