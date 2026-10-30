use crate::core::unified_market_state::UnifiedMarketState;
use crate::liquidity::order_book_depth_validator::OrderBookDepthValidator;
use crate::liquidity::order_side::OrderSide;
use crate::macro_breaker::global_macro_circuit_breaker::GlobalMacroCircuitBreaker;
use crate::time::chrono_guard::ChronoGuard;

/// شجرة القرار SSCCC v9.0 — المستويات 0→3
pub struct DecisionCascade {
    macro_breaker: GlobalMacroCircuitBreaker,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CascadeVerdict {
    Pass,
    RejectLevel0,
    RejectLevel1,
    RejectLevel2,
    RejectLevel3,
}

impl DecisionCascade {
    pub fn new() -> Self {
        Self {
            macro_breaker: GlobalMacroCircuitBreaker::new(),
        }
    }

    pub fn level0_macro(
        &self,
        btc_change_3s_scaled: i64,
        local_bucket_ok: bool,
    ) -> CascadeVerdict {
        if self.macro_breaker.check_btc_shock_and_halt(btc_change_3s_scaled) {
            return CascadeVerdict::RejectLevel0;
        }
        if self.macro_breaker.is_halted() || !local_bucket_ok {
            return CascadeVerdict::RejectLevel0;
        }
        CascadeVerdict::Pass
    }

    pub fn level1_battalion(consensus: f64, macro_risk: f64) -> CascadeVerdict {
        if macro_risk >= 0.20 || consensus < 90.0 {
            return CascadeVerdict::RejectLevel1;
        }
        CascadeVerdict::Pass
    }

    pub fn level2_environment(
        chrono: &ChronoGuard,
        order_side: OrderSide,
        order_size: f64,
        bid_depth: f64,
        ask_depth: f64,
        state: &UnifiedMarketState,
    ) -> CascadeVerdict {
        if !state.is_safe_to_execute() {
            return CascadeVerdict::RejectLevel2;
        }
        if chrono.get_safe_exchange_timestamp().is_err() {
            return CascadeVerdict::RejectLevel2;
        }
        if OrderBookDepthValidator::validate_depth_or_reject(
            order_side,
            order_size,
            bid_depth,
            ask_depth,
        )
        .is_err()
        {
            return CascadeVerdict::RejectLevel2;
        }
        CascadeVerdict::Pass
    }

    pub fn level3_execution(momentum_consensus: f64, sovereign_score: f64) -> CascadeVerdict {
        if momentum_consensus < 85.0 || sovereign_score < 90.0 {
            return CascadeVerdict::RejectLevel3;
        }
        CascadeVerdict::Pass
    }
}

impl Default for DecisionCascade {
    fn default() -> Self {
        Self::new()
    }
}
