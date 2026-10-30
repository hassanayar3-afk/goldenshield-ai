use std::collections::HashMap;

use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use sha2::Sha256;

use super::exchange_rules::{ExchangeInfoResponse, ExchangeRulesCache};
use super::rest_client::BinanceRestClient;
use crate::config::env_settings::SaqrSettings;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Clone, Deserialize)]
pub struct Balance {
    pub asset: String,
    pub free: String,
    pub locked: String,
}

#[derive(Debug, Deserialize)]
pub struct AccountResponse {
    pub balances: Vec<Balance>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderResponse {
    pub symbol: String,
    pub orderId: u64,
    pub status: String,
    pub executedQty: String,
    pub cummulativeQuoteQty: Option<String>,
    pub side: String,
    pub price: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MyTrade {
    pub symbol: String,
    pub id: u64,
    pub price: String,
    pub qty: String,
    pub quoteQty: String,
    pub time: u64,
    pub isBuyer: bool,
}

#[derive(Debug, Deserialize)]
struct TickerPriceRow {
    symbol: String,
    price: String,
}

pub struct BinanceSignedClient {
    rest: BinanceRestClient,
    http: reqwest::Client,
    settings: SaqrSettings,
    pub rules_cache: ExchangeRulesCache,
    time_offset_ms: std::sync::atomic::AtomicI64,
}

impl BinanceSignedClient {
    pub fn new(settings: SaqrSettings) -> Self {
        let rest = BinanceRestClient::new(settings.binance.clone());
        Self {
            rest,
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(25))
                .build()
                .unwrap_or_default(),
            settings,
            rules_cache: ExchangeRulesCache::new(),
            time_offset_ms: std::sync::atomic::AtomicI64::new(0),
        }
    }

    pub fn configured(&self) -> bool {
        !self.settings.api_key.is_empty() && !self.settings.api_secret.is_empty()
    }

    pub async fn sync_time(&self) -> Result<(), String> {
        let url = self.rest.time_url();
        let resp: crate::binance::http_client::ServerTimeResponse = self
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
        let local = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as i64)
            .unwrap_or(0);
        let offset = resp.server_time as i64 - local;
        self.time_offset_ms
            .store(offset, std::sync::atomic::Ordering::Relaxed);
        Ok(())
    }

    fn timestamp_ms(&self) -> u64 {
        let local = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        let off = self.time_offset_ms.load(std::sync::atomic::Ordering::Relaxed);
        (local as i64 + off).max(0) as u64
    }

    fn sign_query(&self, query: &str) -> String {
        let mut mac =
            HmacSha256::new_from_slice(self.settings.api_secret.as_bytes()).expect("hmac key");
        mac.update(query.as_bytes());
        hex::encode(mac.finalize().into_bytes())
    }

    async fn signed_get(&self, path: &str, params: &[( &str, String)]) -> Result<String, String> {
        let mut parts: Vec<String> = params
            .iter()
            .map(|(k, v)| format!("{k}={v}"))
            .collect();
        parts.push(format!("timestamp={}", self.timestamp_ms()));
        parts.push(format!(
            "recvWindow={}",
            self.settings.binance.recv_window_ms
        ));
        let query = parts.join("&");
        let sig = self.sign_query(&query);
        let url = format!(
            "{}{}?{}&signature={sig}",
            self.settings.binance.rest_base_url.trim_end_matches('/'),
            path,
            query
        );
        let resp = self
            .http
            .get(url)
            .header("X-MBX-APIKEY", &self.settings.api_key)
            .send()
            .await
            .map_err(|e| e.to_string())?;
        let status = resp.status();
        let body = resp.text().await.map_err(|e| e.to_string())?;
        if !status.is_success() {
            return Err(format!("Binance {status}: {body}"));
        }
        Ok(body)
    }

    async fn signed_post(&self, path: &str, params: &[( &str, String)]) -> Result<String, String> {
        let mut parts: Vec<String> = params
            .iter()
            .map(|(k, v)| format!("{k}={v}"))
            .collect();
        parts.push(format!("timestamp={}", self.timestamp_ms()));
        parts.push(format!(
            "recvWindow={}",
            self.settings.binance.recv_window_ms
        ));
        let query = parts.join("&");
        let sig = self.sign_query(&query);
        let url = format!(
            "{}{}?{}&signature={sig}",
            self.settings.binance.rest_base_url.trim_end_matches('/'),
            path,
            query
        );
        let resp = self
            .http
            .post(url)
            .header("X-MBX-APIKEY", &self.settings.api_key)
            .send()
            .await
            .map_err(|e| e.to_string())?;
        let status = resp.status();
        let body = resp.text().await.map_err(|e| e.to_string())?;
        if !status.is_success() {
            return Err(format!("Binance {status}: {body}"));
        }
        Ok(body)
    }

    pub async fn refresh_exchange_rules(&self) -> Result<(), String> {
        let url = format!(
            "{}/api/v3/exchangeInfo",
            self.settings.binance.rest_base_url.trim_end_matches('/')
        );
        let raw: ExchangeInfoResponse = self
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
        self.rules_cache.upsert_from_exchange_info(&raw);
        Ok(())
    }

    pub async fn account(&self) -> Result<AccountResponse, String> {
        let body = self.signed_get("/api/v3/account", &[]).await?;
        serde_json::from_str(&body).map_err(|e| e.to_string())
    }

    pub async fn ticker_prices_map(&self) -> Result<HashMap<String, f64>, String> {
        let url = format!(
            "{}/api/v3/ticker/price",
            self.settings.binance.rest_base_url.trim_end_matches('/')
        );
        let rows: Vec<TickerPriceRow> = self
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
        let mut out = HashMap::new();
        for r in rows {
            if let Ok(p) = r.price.parse::<f64>() {
                out.insert(r.symbol, p);
            }
        }
        Ok(out)
    }

    pub async fn my_trades(&self, symbol: &str, start_time: Option<u64>) -> Result<Vec<MyTrade>, String> {
        let mut params = vec![("symbol", symbol.to_string())];
        if let Some(st) = start_time {
            params.push(("startTime", st.to_string()));
        }
        params.push(("limit", "500".to_string()));
        let body = self.signed_get("/api/v3/myTrades", &params).await?;
        serde_json::from_str(&body).map_err(|e| e.to_string())
    }

    pub async fn market_order(
        &self,
        symbol: &str,
        side: &str,
        quantity: &str,
    ) -> Result<OrderResponse, String> {
        let params = vec![
            ("symbol", symbol.to_string()),
            ("side", side.to_string()),
            ("type", "MARKET".to_string()),
            ("quantity", quantity.to_string()),
        ];
        let body = self.signed_post("/api/v3/order", &params).await?;
        serde_json::from_str(&body).map_err(|e| e.to_string())
    }

    /// MARKET BUY spending quote asset (USDT) — Spot / Testnet signed order.
    pub async fn market_buy_quote_usdt(
        &self,
        symbol: &str,
        quote_usdt: f64,
    ) -> Result<OrderResponse, String> {
        if quote_usdt < 5.0 {
            return Err("quote_usdt_below_min".into());
        }
        let quote = format!("{quote_usdt:.2}");
        let params = vec![
            ("symbol", symbol.to_string()),
            ("side", "BUY".to_string()),
            ("type", "MARKET".to_string()),
            ("quoteOrderQty", quote),
        ];
        let body = self.signed_post("/api/v3/order", &params).await?;
        serde_json::from_str(&body).map_err(|e| e.to_string())
    }
}
