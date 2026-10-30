use super::order_side::OrderSide;

pub struct OrderBookDepthValidator;

impl OrderBookDepthValidator {
    const MIN_LIQUIDITY_MULTIPLIER: f64 = 5.0;

    pub fn validate_depth_or_reject(
        order_side: OrderSide,
        order_size: f64,
        available_bid_depth_sum: f64,
        available_ask_depth_sum: f64,
    ) -> Result<(), &'static str> {
        let required_depth = order_size * Self::MIN_LIQUIDITY_MULTIPLIER;
        let relevant_depth = match order_side {
            OrderSide::Buy => available_ask_depth_sum,
            OrderSide::Sell => available_bid_depth_sum,
        };

        if relevant_depth < required_depth {
            return Err(
                "LIQUIDITY_VACUUM_PANIC: Target Order Book Depth is below 5x required multiplier. Execution Aborted.",
            );
        }
        Ok(())
    }
}
