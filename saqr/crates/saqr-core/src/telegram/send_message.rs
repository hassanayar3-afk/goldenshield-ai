use serde::Serialize;

use super::dispatcher::TelegramDispatcher;
use super::get_updates::{parse_updates, TelegramInboundMessage, TelegramPollBatch};
use crate::config::env_settings::TelegramSettings;

#[derive(Serialize)]
struct SendMessageBody<'a> {
    chat_id: &'a str,
    text: &'a str,
    parse_mode: &'a str,
}

#[derive(Serialize)]
struct EditMessageBody<'a> {
    chat_id: &'a str,
    message_id: i64,
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

    /// Sends HTML text; returns Telegram `message_id` for live board edits.
    pub async fn send_text_return_id(&self, text: &str) -> Result<i64, String> {
        if self.dispatcher.default_chat_id().is_empty() {
            return Err("TELEGRAM_CHAT_ID missing".into());
        }
        let url = self.dispatcher.api_send_url();
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
        let status = resp.status();
        let raw = resp.text().await.unwrap_or_default();
        if !status.is_success() {
            return Err(format!("Telegram HTTP {status}: {raw}"));
        }
        let v: serde_json::Value =
            serde_json::from_str(&raw).map_err(|e| format!("Telegram JSON: {e}"))?;
        v.get("result")
            .and_then(|r| r.get("message_id"))
            .and_then(|m| m.as_i64())
            .ok_or_else(|| format!("Telegram send missing message_id: {raw}"))
    }

    pub async fn edit_text(&self, message_id: i64, text: &str) -> Result<(), String> {
        self.edit_dashboard(message_id, text, &serde_json::json!({})).await
    }

    pub async fn send_dashboard(&self, text: &str, keyboard: &serde_json::Value) -> Result<i64, String> {
        let url = self.dispatcher.api_send_url();
        let body = serde_json::json!({
            "chat_id": self.dispatcher.default_chat_id(),
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        });
        let resp = self.http.post(&url).json(&body).send().await.map_err(|e| e.to_string())?;
        let status = resp.status();
        let raw = resp.text().await.unwrap_or_default();
        if !status.is_success() {
            return Err(format!("Telegram HTTP {status}: {raw}"));
        }
        let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| format!("Telegram JSON: {e}"))?;
        v.get("result")
            .and_then(|r| r.get("message_id"))
            .and_then(|m| m.as_i64())
            .ok_or_else(|| format!("Telegram send missing message_id: {raw}"))
    }

    pub async fn edit_dashboard(
        &self,
        message_id: i64,
        text: &str,
        keyboard: &serde_json::Value,
    ) -> Result<(), String> {
        if self.dispatcher.default_chat_id().is_empty() {
            return Err("TELEGRAM_CHAT_ID missing".into());
        }
        let url = self.dispatcher.api_edit_message_url();
        let body = serde_json::json!({
            "chat_id": self.dispatcher.default_chat_id(),
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        });
        let resp = self
            .http
            .post(&url)
            .json(&body)
            .send()
            .await
            .map_err(|e| e.to_string())?;
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        if status.is_success() {
            return Ok(());
        }
        if body.contains("message is not modified") {
            return Ok(());
        }
        Err(format!("Telegram edit HTTP {status}: {body}"))
    }

    pub async fn answer_callback(&self, query_id: &str, text: Option<&str>) -> Result<(), String> {
        let url = self.dispatcher.api_answer_callback_url();
        let body = serde_json::json!({
            "callback_query_id": query_id,
            "text": text.unwrap_or(""),
            "show_alert": false,
        });
        let resp = self.http.post(&url).json(&body).send().await.map_err(|e| e.to_string())?;
        if !resp.status().is_success() {
            let status = resp.status();
            let raw = resp.text().await.unwrap_or_default();
            return Err(format!("answerCallbackQuery {status}: {raw}"));
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
        if chat_id.trim() == allowed.trim() {
            return true;
        }
        match (allowed.parse::<i64>(), chat_id.parse::<i64>()) {
            (Ok(a), Ok(c)) => a != 0 && a == c,
            _ => false,
        }
    }

    /// Long-poll messages + inline keyboard callbacks.
    pub async fn poll_inbound(
        &self,
        offset: i64,
        timeout_secs: u8,
    ) -> Result<(Vec<TelegramInboundMessage>, i64), String> {
        let batch = self.poll_updates(offset, timeout_secs).await?;
        Ok((batch.messages, batch.next_offset))
    }

    pub async fn poll_updates(&self, offset: i64, timeout_secs: u8) -> Result<TelegramPollBatch, String> {
        if !self.is_configured() {
            return Ok(TelegramPollBatch {
                next_offset: offset,
                ..Default::default()
            });
        }
        let url = self.dispatcher.get_updates_url();
        let resp = self
            .http
            .get(&url)
            .query(&[
                ("offset", offset.to_string()),
                ("timeout", timeout_secs.to_string()),
                ("allowed_updates", "[\"message\",\"callback_query\"]".into()),
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
        let mut batch = parse_updates(&body)?;
        if batch.next_offset == 0 {
            batch.next_offset = offset;
        }
        Ok(batch)
    }
}
