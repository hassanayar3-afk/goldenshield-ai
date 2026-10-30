#[derive(Debug, Clone)]
pub struct SelectedBattalion {
    pub symbol: String,
    pub volume_acceleration: f64,
    pub consensus_score: f64,
    pub entry_price: f64,
    pub atr_volatility: f64,
    pub win_rate_historical: f64,
    pub win_loss_ratio: f64,
}
