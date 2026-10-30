use super::self_trade_prevention_mode::SelfTradePreventionMode;

pub struct CompliantOrderRouter;

impl CompliantOrderRouter {
    pub fn build_safe_order_payload(
        symbol: &str,
        side: &str,
        price_scaled: i64,
        qty_scaled: i64,
        stp_mode: SelfTradePreventionMode,
    ) -> String {
        format!(
            r#"{{"symbol":"{symbol}","side":"{side}","type":"LIMIT","timeInForce":"IOC","price":"{price}","quantity":"{qty}","selfTradePreventionMode":"{stp}"}}"#,
            symbol = symbol,
            side = side,
            price = price_scaled as f64 / 100_000_000.0,
            qty = qty_scaled as f64 / 100_000_000.0,
            stp = stp_mode.as_binance_str(),
        )
    }
}
