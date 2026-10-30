use saqr_core::conquest::composite_exit::{CompositeExitEngine, ExitSignal};
use saqr_core::liquidity::order_book_depth_validator::OrderBookDepthValidator;
use saqr_core::liquidity::order_side::OrderSide;
use saqr_core::momentum::apex_emperor_core::ApexEmperorCore;

#[test]
fn depth_validator_rejects_thin_book() {
    let err = OrderBookDepthValidator::validate_depth_or_reject(
        OrderSide::Buy,
        100.0,
        1000.0,
        200.0,
    );
    assert!(err.is_err());
}

#[test]
fn apex_consensus_respects_volatility_cap() {
    let core = ApexEmperorCore::new();
    assert!(!core.evaluate_consensus(90_000_000, 90_000_000, 200_000_000));
}

#[test]
fn composite_exit_secures_loot_band() {
    assert_eq!(
        CompositeExitEngine::evaluate(0.5, 1.0, 5.0),
        ExitSignal::SecureLoot
    );
}
