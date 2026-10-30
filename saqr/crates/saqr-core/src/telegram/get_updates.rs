use serde::Deserialize;

#[derive(Debug, Clone)]
pub struct TelegramInboundMessage {
    pub update_id: i64,
    pub chat_id: String,
    pub text: String,
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
}

#[derive(Deserialize)]
struct TgMessage {
    chat: TgChat,
    text: Option<String>,
}

#[derive(Deserialize)]
struct TgChat {
    id: i64,
}

pub fn parse_updates(body: &str) -> Result<Vec<TelegramInboundMessage>, String> {
    let parsed: UpdatesResponse = serde_json::from_str(body).map_err(|e| e.to_string())?;
    if !parsed.ok {
        return Err("telegram ok=false".into());
    }
    let mut out = Vec::new();
    for item in parsed.result {
        let Some(msg) = item.message else { continue };
        let Some(text) = msg.text else { continue };
        let trimmed = text.trim();
        if trimmed.is_empty() {
            continue;
        }
        out.push(TelegramInboundMessage {
            update_id: item.update_id,
            chat_id: msg.chat.id.to_string(),
            text: trimmed.to_string(),
        });
    }
    Ok(out)
}
