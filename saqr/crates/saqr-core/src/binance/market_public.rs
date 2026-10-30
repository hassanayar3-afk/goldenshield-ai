use std::collections::HashMap;

use serde::Deserialize;

use crate::config::env_settings::SaqrSettings;

#[derive(Debug, Deserialize)]
pub struct KlineRow(
    String,
    String,
    String,
    String,
    String,
    String,
    u64,
    String,
    u64,
    String,
    String,
    String,
);

#[derive(Debug, Deserialize)]
pub struct Ticker24h {
    pub symbol: String,
    #[serde(rename = "quoteVolume")]
    pub quote_volume: String,
    #[serde(rename = "lastPrice")]
    pub last_price: String,
    #[serde(rename = "priceChangePercent")]
    pub price_change_percent: String,
}

pub struct BinancePublicMarket {
    http: reqwest::Client,
    base_url: String,
}

impl BinancePublicMarket {
    pub fn new(settings: &SaqrSettings) -> Self {
        let base_url = if settings.is_paper_trading() {
            settings.market_rest_url.clone()
        } else {
            settings.binance.rest_base_url.clone()
        };
        Self {
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(20))
                .build()
                .unwrap_or_default(),
            base_url: base_url.trim_end_matches('/').to_string(),
        }
    }

    pub async fn ping(&self) -> Result<(), String> {
        let url = format!("{}/api/v3/ping", self.base_url);
        self.http
            .get(url)
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?;
        Ok(())
    }

    pub async fn price(&self, symbol: &str) -> Result<f64, String> {
        let url = format!("{}/api/v3/ticker/price?symbol={symbol}", self.base_url);
        #[derive(Deserialize)]
        struct R {
            price: String,
        }
        let r: R = self
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
        r.price.parse().map_err(|e: std::num::ParseFloatError| e.to_string())
    }

    pub async fn prices_map(&self, symbols: &[&str]) -> HashMap<String, f64> {
        let mut out = HashMap::new();
        for s in symbols {
            if let Ok(p) = self.price(s).await {
                out.insert((*s).to_string(), p);
            }
        }
        out
    }

    pub async fn klines(&self, symbol: &str, interval: &str, limit: u16) -> Result<Vec<KlineRow>, String> {
        let url = format!(
            "{}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
            self.base_url
        );
        self.http
            .get(url)
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?
            .json()
            .await
            .map_err(|e| e.to_string())
    }

    pub async fn tickers_24h(&self) -> Result<Vec<Ticker24h>, String> {
        let url = format!("{}/api/v3/ticker/24hr", self.base_url);
        self.http
            .get(url)
            .send()
            .await
            .map_err(|e| e.to_string())?
            .error_for_status()
            .map_err(|e| e.to_string())?
            .json()
            .await
            .map_err(|e| e.to_string())
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }
}

pub fn rsi_from_closes(closes: &[f64], period: usize) -> Option<f64> {
    if closes.len() <= period {
        return None;
    }
    let mut gains = 0.0;
    let mut losses = 0.0;
    let start = closes.len() - period;
    for i in start..closes.len() {
        let diff = closes[i] - closes[i - 1];
        if diff >= 0.0 {
            gains += diff;
        } else {
            losses -= diff;
        }
    }
    if losses == 0.0 {
        return Some(100.0);
    }
    let rs = gains / losses;
    Some(100.0 - (100.0 / (1.0 + rs)))
}

pub fn closes_from_klines(rows: &[KlineRow]) -> Vec<f64> {
    rows.iter()
        .filter_map(|k| k.4.parse::<f64>().ok())
        .collect()
}
