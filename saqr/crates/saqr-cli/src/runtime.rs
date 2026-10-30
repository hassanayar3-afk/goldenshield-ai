use std::collections::HashSet;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use parking_lot::Mutex;
use saqr_core::binance::market_public::BinancePublicMarket;
use saqr_core::binance::mirror::{build_mirror, BinanceMirrorPayload};
use saqr_core::binance::signed_api::BinanceSignedClient;
use saqr_core::config::env_settings::SaqrSettings;
use saqr_core::paper::PaperEngine;
use saqr_core::telegram::send_message::TelegramClient;

#[derive(Clone)]
pub struct SharedRuntime {
    pub settings: Arc<SaqrSettings>,
    pub binance: Arc<BinanceSignedClient>,
    pub market: Arc<BinancePublicMarket>,
    pub paper: Arc<PaperEngine>,
    pub telegram: Arc<TelegramClient>,
    pub bot_running: Arc<AtomicBool>,
    pub last_mirror: Arc<Mutex<Option<BinanceMirrorPayload>>>,
    pub telegram_board_message_id: Arc<Mutex<Option<i64>>>,
    pub auto_entered_symbols: Arc<Mutex<HashSet<String>>>,
    pub telegram_panel_section: Arc<Mutex<String>>,
}

impl SharedRuntime {
    pub fn new(settings: SaqrSettings) -> Self {
        let bot_running = Arc::new(AtomicBool::new(true));
        let paper = Arc::new(PaperEngine::new(settings.initial_balance_usd));
        Self {
            settings: Arc::new(settings.clone()),
            binance: Arc::new(BinanceSignedClient::new(settings.clone())),
            market: Arc::new(BinancePublicMarket::new(&settings)),
            paper,
            telegram: Arc::new(TelegramClient::new(settings.telegram.clone())),
            bot_running,
            last_mirror: Arc::new(Mutex::new(None)),
            telegram_board_message_id: Arc::new(Mutex::new(None)),
            auto_entered_symbols: Arc::new(Mutex::new(HashSet::new())),
            telegram_panel_section: Arc::new(Mutex::new("home".into())),
        }
    }

    pub fn bot_is_running(&self) -> bool {
        self.bot_running.load(Ordering::Relaxed)
    }

    pub fn set_bot_running(&self, on: bool) {
        self.bot_running.store(on, Ordering::Relaxed);
    }

    pub async fn refresh_mirror(&self) -> BinanceMirrorPayload {
        let fallback = self.last_mirror.lock().clone();
        let payload = if self.settings.is_paper_trading() {
            self.paper
                .build_mirror(
                    &self.market,
                    &self.settings.symbol,
                    self.bot_is_running(),
                )
                .await
        } else {
            build_mirror(
                &self.binance,
                &self.settings,
                self.bot_is_running(),
                fallback.as_ref(),
            )
            .await
        };
        *self.last_mirror.lock() = Some(payload.clone());
        payload
    }
}
