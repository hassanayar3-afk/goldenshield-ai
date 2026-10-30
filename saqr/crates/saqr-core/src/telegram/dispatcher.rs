use crate::config::env_settings::TelegramSettings;

/// Priority 0 = صفقات حرجة | Priority 1 = تقارير
#[derive(Debug, Clone)]
pub enum TelegramPriority {
    CriticalTrade = 0,
    SummaryReport = 1,
}

pub struct TelegramDispatcher {
    settings: TelegramSettings,
}

impl TelegramDispatcher {
    pub fn new(settings: TelegramSettings) -> Self {
        Self { settings }
    }

    pub fn api_send_url(&self) -> String {
        format!(
            "https://api.telegram.org/bot{}/sendMessage",
            self.settings.bot_token
        )
    }

    pub fn fallback_api_send_url(&self) -> Option<String> {
        self.settings
            .secondary_bot_token
            .as_ref()
            .map(|t| format!("https://api.telegram.org/bot{t}/sendMessage"))
    }

    pub fn default_chat_id(&self) -> &str {
        &self.settings.chat_id
    }
}
