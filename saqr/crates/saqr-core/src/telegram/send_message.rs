use serde::Serialize;

use super::dispatcher::TelegramDispatcher;
use crate::config::env_settings::TelegramSettings;

#[derive(Serialize)]
struct SendMessageBody<'a> {
    chat_id: &'a str,
    text: &'a str,
    parse_mode: &'a str,
}

pub struct TelegramClient {
    dispatcher: TelegramDispatcher,
    http: reqwest::Client,
}

impl TelegramClient {
    pub fn new(settings: TelegramSettings) -> Self {
        Self {
            dispatcher: TelegramDispatcher::new(settings),
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(25))
                .build()
                .unwrap_or_default(),
        }
    }

    pub fn is_configured(&self) -> bool {
        let url = self.dispatcher.api_send_url();
        !self.dispatcher.default_chat_id().is_empty()
            && url.starts_with("https://api.telegram.org/bot")
            && url.len() > 45
    }

    pub async fn send_text(&self, text: &str) -> Result<(), String> {
        if self.dispatcher.default_chat_id().is_empty() {
            return Err("TELEGRAM_CHAT_ID missing".into());
        }
        let url = self.dispatcher.api_send_url();
        if url.contains("bot/sendMessage") && !url.contains("bot") {
            return Err("TELEGRAM_BOT_TOKEN missing".into());
        }
        let token_missing = url == "https://api.telegram.org/bot/sendMessage";
        if token_missing {
            return Err("TELEGRAM_BOT_TOKEN missing".into());
        }

        let body = SendMessageBody {
            chat_id: self.dispatcher.default_chat_id(),
            text,
            parse_mode: "HTML",
        };

        let resp = self
            .http
            .post(&url)
            .json(&body)
            .send()
            .await
            .map_err(|e| e.to_string())?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(format!("Telegram HTTP {status}: {body}"));
        }
        Ok(())
    }
}
