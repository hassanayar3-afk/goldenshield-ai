use crate::config::env_settings::BinanceEndpoints;

/// WebSocket stream URL builder
pub struct BinanceWsStream {
    endpoints: BinanceEndpoints,
}

impl BinanceWsStream {
    pub fn new(endpoints: BinanceEndpoints) -> Self {
        Self { endpoints }
    }

    pub fn trade_stream_url(&self, symbol_lower: &str) -> String {
        format!(
            "{}/ws/{}@trade",
            self.endpoints.ws_base_url.trim_end_matches('/'),
            symbol_lower
        )
    }

    pub fn depth_stream_url(&self, symbol_lower: &str) -> String {
        format!(
            "{}/ws/{}@depth10@100ms",
            self.endpoints.ws_base_url.trim_end_matches('/'),
            symbol_lower
        )
    }
}
