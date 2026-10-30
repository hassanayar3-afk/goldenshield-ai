/// 128-bit Fixed-Point Precision — Scale 10^8
pub const FP_SCALE: u128 = 100_000_000;

pub fn mul_scaled(a: u128, b: u128) -> u128 {
    (a.saturating_mul(b)) / FP_SCALE
}

pub fn add_scaled(a: u128, b: u128) -> u128 {
    a.saturating_add(b)
}

pub fn risk_ratio_scaled(numerator: u128, denominator: u128) -> u128 {
    if denominator == 0 {
        return 0;
    }
    (numerator.saturating_mul(FP_SCALE)) / denominator
}
