use crate::config::env_settings::BinanceEndpoints;

/// عميل REST — يبني URLs من الإعدادات فقط (لا أسرار في الكود)
pub struct BinanceRestClient {
    endpoints: BinanceEndpoints,
}

impl BinanceRestClient {
    pub fn new(endpoints: BinanceEndpoints) -> Self {
        Self { endpoints }
    }

    pub fn ping_url(&self) -> String {
        format!("{}/api/v3/ping", self.endpoints.rest_base_url)
    }

    pub fn time_url(&self) -> String {
        format!("{}/api/v3/time", self.endpoints.rest_base_url)
    }

    pub fn open_orders_url(&self) -> String {
        format!("{}/api/v3/openOrders", self.endpoints.rest_base_url)
    }
}
