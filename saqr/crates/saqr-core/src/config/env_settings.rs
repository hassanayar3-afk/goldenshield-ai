use std::env;

#[derive(Debug, Clone)]
pub struct BinanceEndpoints {
    pub rest_base_url: String,
    pub ws_base_url: String,
    pub spot_web_url: String,
    pub recv_window_ms: u64,
    pub testnet: bool,
}

#[derive(Debug, Clone)]
pub struct TelegramSettings {
    pub bot_token: String,
    pub chat_id: String,
    pub secondary_bot_token: Option<String>,
}

#[derive(Debug, Clone)]
pub struct CloudServerSettings {
    pub host: String,
    pub port: u16,
    pub ssh_user: String,
    pub password: String,
    pub public_dashboard_url: String,
}

#[derive(Debug, Clone)]
pub struct SaqrSettings {
    pub mode: String,
    pub require_integrated_demo: bool,
    pub enable_trading: bool,
    pub initial_balance_usd: f64,
    pub symbol: String,
    pub api_key: String,
    pub api_secret: String,
    pub binance: BinanceEndpoints,
    pub market_rest_url: String,
    pub market_ws_url: String,
    pub telegram: TelegramSettings,
    pub cloud: CloudServerSettings,
    pub web_bind_host: String,
    pub web_bind_port: u16,
    pub web_enabled: bool,
    pub telegram_bridge_enabled: bool,
    pub telegram_control_panel: bool,
    pub signal_interval_secs: u64,
    pub integration_interval_secs: u64,
}

impl SaqrSettings {
    pub fn from_env() -> Self {
        let mode = env::var("SAQR_MODE").unwrap_or_else(|_| "paper".into());
        let paper = Self::is_paper_mode_str(&mode);
        let testnet = if paper {
            false
        } else {
            env_bool("BINANCE_TESTNET", true)
        };

        let market_rest = env::var("BINANCE_MARKET_REST_URL")
            .ok()
            .filter(|s| !s.trim().is_empty())
            .or_else(|| env::var("BINANCE_REST_URL").ok())
            .unwrap_or_else(|| "https://api.binance.com".into());
        let market_ws = env::var("BINANCE_MARKET_WS_URL")
            .ok()
            .filter(|s| !s.trim().is_empty())
            .or_else(|| env::var("BINANCE_WS_URL").ok())
            .map(|s| normalize_binance_ws_base(&s))
            .unwrap_or_else(|| "wss://stream.binance.com:9443".into());

        let rest = if paper {
            market_rest.clone()
        } else {
            env::var("BINANCE_REST_URL").unwrap_or_else(|_| {
                if testnet {
                    "https://testnet.binance.vision".into()
                } else {
                    "https://api.binance.com".into()
                }
            })
        };

        let ws = if paper {
            market_ws.clone()
        } else {
            env::var("BINANCE_WS_URL")
                .map(|s| normalize_binance_ws_base(&s))
                .unwrap_or_else(|_| {
                    if testnet {
                        "wss://stream.testnet.binance.vision".into()
                    } else {
                        "wss://stream.binance.com:9443".into()
                    }
                })
        };

        let telegram_control_panel = env_bool("SAQR_TELEGRAM_CONTROL_PANEL", false);
        let web_enabled = match env::var("SAQR_WEB_ENABLED") {
            Ok(_) => env_bool("SAQR_WEB_ENABLED", true),
            Err(_) => !telegram_control_panel,
        };
        let signal_interval_secs = env::var("SAQR_SIGNAL_INTERVAL_SECS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(if telegram_control_panel { 3 } else { 15 })
            .clamp(2, 300);

        Self {
            mode,
            require_integrated_demo: env_bool("SAQR_REQUIRE_INTEGRATED_DEMO", false),
            enable_trading: env_bool("SAQR_ENABLE_TRADING", true),
            initial_balance_usd: env_f64("SAQR_INITIAL_BALANCE_USD", 5000.0),
            symbol: env::var("SAQR_SYMBOL").unwrap_or_else(|_| "BTCUSDT".into()),
            api_key: env::var("BINANCE_API_KEY").unwrap_or_default(),
            api_secret: env::var("BINANCE_API_SECRET").unwrap_or_default(),
            binance: BinanceEndpoints {
                rest_base_url: rest,
                ws_base_url: ws,
                spot_web_url: env::var("BINANCE_SPOT_WEB_URL").unwrap_or_default(),
                recv_window_ms: env::var("BINANCE_RECV_WINDOW")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(5000),
                testnet,
            },
            market_rest_url: market_rest,
            market_ws_url: market_ws,
            telegram: TelegramSettings {
                bot_token: env::var("TELEGRAM_BOT_TOKEN").unwrap_or_default(),
                chat_id: env::var("TELEGRAM_CHAT_ID").unwrap_or_default(),
                secondary_bot_token: env::var("TELEGRAM_SECONDARY_BOT_TOKEN").ok(),
            },
            cloud: CloudServerSettings {
                host: env::var("CLOUD_SERVER_HOST").unwrap_or_default(),
                port: env_u16("CLOUD_SERVER_PORT", 22),
                ssh_user: env::var("CLOUD_SERVER_SSH_USER").unwrap_or_default(),
                password: env::var("CLOUD_SERVER_PASSWORD").unwrap_or_default(),
                public_dashboard_url: env::var("SAQR_PUBLIC_DASHBOARD_URL").unwrap_or_default(),
            },
            web_bind_host: env::var("SAQR_WEB_BIND_HOST").unwrap_or_else(|_| "127.0.0.1".into()),
            web_bind_port: env_u16("SAQR_WEB_BIND_PORT", 8788),
            telegram_bridge_enabled: env_bool("SAQR_TELEGRAM_BRIDGE", true),
            telegram_control_panel,
            web_enabled,
            signal_interval_secs,
            integration_interval_secs: env::var("SAQR_INTEGRATION_INTERVAL_SECS")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(900),
        }
    }

    pub fn is_paper_trading(&self) -> bool {
        Self::is_paper_mode_str(&self.mode)
    }

    fn is_paper_mode_str(mode: &str) -> bool {
        matches!(
            mode.to_lowercase().as_str(),
            "paper" | "sandbox" | "sim" | "simulation"
        )
    }

    /// تنفيذ أوامر حقيقية على Testnet/Live — معطّل في وضع Paper.
    pub fn live_execution_enabled(&self) -> bool {
        self.enable_trading && !self.is_paper_trading()
    }
}

fn env_bool(key: &str, default: bool) -> bool {
    match env::var(key) {
        Ok(v) => matches!(v.to_lowercase().as_str(), "1" | "true" | "yes" | "on"),
        Err(_) => default,
    }
}

fn env_f64(key: &str, default: f64) -> f64 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u16(key: &str, default: u16) -> u16 {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

/// Accepts `wss://stream.binance.com:9443/ws` and normalizes to stream base.
fn normalize_binance_ws_base(raw: &str) -> String {
    let mut s = raw.trim().trim_end_matches('/').to_string();
    if s.ends_with("/ws") {
        s.truncate(s.len().saturating_sub(3));
        s = s.trim_end_matches('/').to_string();
    }
    s
}
