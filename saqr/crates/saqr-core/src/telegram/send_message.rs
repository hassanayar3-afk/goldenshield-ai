use serde::Serialize;

use super::dispatcher::TelegramDispatcher;
use super::get_updates::{parse_updates, TelegramInboundMessage};
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

    pub fn authorized_chat_id(&self) -> &str {
        self.dispatcher.default_chat_id()
    }

    pub fn chat_is_authorized(&self, chat_id: &str) -> bool {
        let allowed = self.dispatcher.default_chat_id();
        if allowed.is_empty() {
            return false;
        }
        chat_id.trim() == allowed.trim()
    }

    /// Long-poll inbound commands (Telegram → SAQR).
    pub async fn poll_inbound(
        &self,
        offset: i64,
        timeout_secs: u8,
    ) -> Result<(Vec<TelegramInboundMessage>, i64), String> {
        if !self.is_configured() {
            return Ok((Vec::new(), offset));
        }
        let url = self.dispatcher.get_updates_url();
        let resp = self
            .http
            .get(&url)
            .query(&[
                ("offset", offset.to_string()),
                ("timeout", timeout_secs.to_string()),
                ("allowed_updates", "[\"message\"]".into()),
            ])
            .send()
            .await
            .map_err(|e| e.to_string())?;
        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(format!("Telegram getUpdates HTTP {status}: {body}"));
        }
        let body = resp.text().await.map_err(|e| e.to_string())?;
        let messages = parse_updates(&body)?;
        let next = messages
            .iter()
            .map(|m| m.update_id + 1)
            .max()
            .unwrap_or(offset);
        Ok((messages, next))
    }
}
