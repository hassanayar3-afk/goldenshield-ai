/// X-Exchange Liquidity Matrix
pub struct CrossExchangeLiquidityMatrix;

impl CrossExchangeLiquidityMatrix {
    pub fn aggregate_depth_scaled(binance: i64, okx: i64, bybit: i64) -> i64 {
        binance.saturating_add(okx).saturating_add(bybit)
    }
}
