use serde::Deserialize;

#[derive(Debug, Clone)]
pub struct TelegramInboundMessage {
    pub update_id: i64,
    pub chat_id: String,
    pub text: String,
}

#[derive(Debug, Clone)]
pub struct TelegramCallbackQuery {
    pub update_id: i64,
    pub query_id: String,
    pub chat_id: String,
    pub message_id: Option<i64>,
    pub data: String,
}

#[derive(Debug, Clone, Default)]
pub struct TelegramPollBatch {
    pub messages: Vec<TelegramInboundMessage>,
    pub callbacks: Vec<TelegramCallbackQuery>,
    pub next_offset: i64,
}

#[derive(Deserialize)]
struct UpdatesResponse {
    ok: bool,
    result: Vec<UpdateItem>,
}

#[derive(Deserialize)]
struct UpdateItem {
    update_id: i64,
    message: Option<TgMessage>,
    callback_query: Option<TgCallbackQuery>,
}

#[derive(Deserialize)]
struct TgMessage {
    chat: TgChat,
    text: Option<String>,
}

#[derive(Deserialize)]
struct TgCallbackQuery {
    id: String,
    from: Option<TgFrom>,
    message: Option<TgCallbackMessage>,
    data: Option<String>,
}

#[derive(Deserialize)]
struct TgFrom {
    id: i64,
}

#[derive(Deserialize)]
struct TgCallbackMessage {
    message_id: i64,
    chat: TgChat,
}

#[derive(Deserialize)]
struct TgChat {
    id: i64,
}

pub fn parse_updates(body: &str) -> Result<TelegramPollBatch, String> {
    let parsed: UpdatesResponse = serde_json::from_str(body).map_err(|e| e.to_string())?;
    if !parsed.ok {
        return Err("telegram ok=false".into());
    }
    let mut batch = TelegramPollBatch::default();
    for item in parsed.result {
        batch.next_offset = batch.next_offset.max(item.update_id + 1);
        if let Some(cb) = item.callback_query {
            let chat_id = cb
                .message
                .as_ref()
                .map(|m| m.chat.id.to_string())
                .or_else(|| cb.from.as_ref().map(|f| f.id.to_string()))
                .unwrap_or_default();
            let data = cb.data.unwrap_or_default();
            if !chat_id.is_empty() && !data.is_empty() {
                batch.callbacks.push(TelegramCallbackQuery {
                    update_id: item.update_id,
                    query_id: cb.id,
                    chat_id,
                    message_id: cb.message.as_ref().map(|m| m.message_id),
                    data,
                });
            }
            continue;
        }
        let Some(msg) = item.message else {
            continue;
        };
        let Some(text) = msg.text else { continue };
        let trimmed = text.trim();
        if trimmed.is_empty() {
            continue;
        }
        batch.messages.push(TelegramInboundMessage {
            update_id: item.update_id,
            chat_id: msg.chat.id.to_string(),
            text: trimmed.to_string(),
        });
    }
    Ok(batch)
}
