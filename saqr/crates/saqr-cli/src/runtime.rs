use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use parking_lot::Mutex;
use saqr_core::binance::mirror::BinanceMirrorPayload;
use saqr_core::binance::signed_api::BinanceSignedClient;
use saqr_core::config::env_settings::SaqrSettings;
use saqr_core::telegram::send_message::TelegramClient;

#[derive(Clone)]
pub struct SharedRuntime {
    pub settings: Arc<SaqrSettings>,
    pub binance: Arc<BinanceSignedClient>,
    pub telegram: Arc<TelegramClient>,
    pub bot_running: Arc<AtomicBool>,
    pub last_mirror: Arc<Mutex<Option<BinanceMirrorPayload>>>,
}

impl SharedRuntime {
    pub fn new(settings: SaqrSettings) -> Self {
        let bot_running = Arc::new(AtomicBool::new(true));
        Self {
            settings: Arc::new(settings.clone()),
            binance: Arc::new(BinanceSignedClient::new(settings.clone())),
            telegram: Arc::new(TelegramClient::new(settings.telegram.clone())),
            bot_running,
            last_mirror: Arc::new(Mutex::new(None)),
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
        let payload = saqr_core::binance::mirror::build_mirror(
            &self.binance,
            &self.settings,
            self.bot_is_running(),
            fallback.as_ref(),
        )
        .await;
        *self.last_mirror.lock() = Some(payload.clone());
        payload
    }
}
