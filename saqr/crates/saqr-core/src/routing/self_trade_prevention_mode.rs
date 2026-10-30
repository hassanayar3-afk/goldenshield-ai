#[derive(Debug, Clone, Copy)]
pub enum SelfTradePreventionMode {
    ExpireMaker,
    ExpireTaker,
    ExpireBoth,
}

impl SelfTradePreventionMode {
    pub fn as_binance_str(self) -> &'static str {
        match self {
            SelfTradePreventionMode::ExpireMaker => "EXPIRE_MAKER",
            SelfTradePreventionMode::ExpireTaker => "EXPIRE_TAKER",
            SelfTradePreventionMode::ExpireBoth => "EXPIRE_BOTH",
        }
    }
}
