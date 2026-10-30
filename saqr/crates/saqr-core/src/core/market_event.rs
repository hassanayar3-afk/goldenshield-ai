#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct MarketEvent {
    pub symbol_hash: u64,
    pub price_scaled: i64,
    pub volume_scaled: i64,
    pub is_buyer_maker: bool,
    pub timestamp_ns: u64,
}
