/// MVRS — Micro-Volatility Regime Shift
pub struct MvrsPredictor;

impl MvrsPredictor {
    pub fn entropy_burst_scaled(order_book_entropy_scaled: u32, flow_momentum_scaled: i64) -> u32 {
        let combined = order_book_entropy_scaled as u64 + flow_momentum_scaled.unsigned_abs();
        combined.min(u32::MAX as u64) as u32
    }
}
