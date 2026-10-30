use serde::Deserialize;

use super::rest_client::BinanceRestClient;
use crate::config::env_settings::SaqrSettings;

#[derive(Debug, Deserialize)]
struct PingResponse {}

#[derive(Debug, Deserialize)]
pub struct ServerTimeResponse {
    #[serde(rename = "serverTime")]
    pub server_time: u64,
}

#[derive(Debug, Deserialize)]
struct TickerPriceResponse {
    price: String,
}

pub struct BinanceHttpClient {
    rest: BinanceRestClient,
    http: reqwest::Client,
    settings: SaqrSettings,
}

impl BinanceHttpClient {
    pub fn new(settings: SaqrSettings) -> Self {
        let rest = BinanceRestClient::new(settings.binance.clone());
        Self {
            rest,
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(20))
                .build()
                .unwrap_or_default(),
            settings,
        }
    }

    pub async fn ping(&self) -> Result<(), String> {
        let url = self.rest.ping_url();
        self.http
            .get(url)
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?;
        Ok(())
    }

    pub async fn server_time(&self) -> Result<u64, String> {
        let url = self.rest.time_url();
        let resp: ServerTimeResponse = self
            .http
            .get(url)
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?
            .json()
            .await
            .map_err(|e| e.to_string())?;
        Ok(resp.server_time)
    }

    pub async fn ticker_price(&self) -> Result<String, String> {
        let url = format!(
            "{}/api/v3/ticker/price?symbol={}",
            self.settings.binance.rest_base_url.trim_end_matches('/'),
            self.settings.symbol
        );
        let resp: TickerPriceResponse = self
            .http
            .get(url)
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?
            .json()
            .await
            .map_err(|e| e.to_string())?;
        Ok(resp.price)
    }

    pub fn mode_label(&self) -> &'static str {
        if self.settings.binance.testnet {
            "Binance Testnet (Demo)"
        } else {
            "Binance Live"
        }
    }
}
