use std::sync::Arc;

use saqr_core::telegram::anti_flood::TelegramAntiFlood;

use crate::control_actions;
use crate::runtime::SharedRuntime;

const HELP_AR: &str = "🦅 <b>صقر SAQR v6.2.3</b> — أوامر الجسر\n\
/status أو <code>رصيد</code> — ملخص الرصيد والصفقات\n\
/price — سعر BTCUSDT حي\n\
/pause — إيقاف البوت | /resume — تشغيل\n\
/buy — دخول Paper BTC (2%)\n\
/close_win — إغلاق الرابحة | /close_loss — الخاسرة\n\
/emergency — إغلاق طوارئ لكل المراكز\n\
/help — هذه القائمة\n\
📡 سوق: api.binance.com · تنفيذ: Paper Sandbox";

pub fn spawn_bidirectional_bridge(rt: Arc<SharedRuntime>) {
    if !rt.settings.telegram_bridge_enabled {
        tracing::info!("Telegram bidirectional bridge disabled (SAQR_TELEGRAM_BRIDGE=false)");
        return;
    }
    if !rt.telegram.is_configured() {
        tracing::warn!("Telegram bridge skipped — TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing");
        return;
    }
    tokio::spawn(async move {
        run_bridge_loop(rt).await;
    });
}

async fn run_bridge_loop(rt: Arc<SharedRuntime>) {
    let flood = TelegramAntiFlood::new();
    let mut offset: i64 = 0;
    tracing::info!("Telegram ⇄ SAQR bidirectional bridge active (long poll)");
    let _ = rt
        .telegram
        .send_text(
            "🦅 <b>صقر SAQR v6.2.3</b>\n✅ الجسر الثنائي نشط\nTelegram ⇄ Binance (سوق حي) ⇄ Terminal\nPaper Sandbox · أرسل /help",
        )
        .await;

    loop {
        match rt.telegram.poll_inbound(offset, 25).await {
            Ok((messages, next)) => {
                offset = next;
                flood.reset_on_success();
                for msg in messages {
                    if !rt.telegram.chat_is_authorized(&msg.chat_id) {
                        tracing::warn!("ignored Telegram chat {}", msg.chat_id);
                        continue;
                    }
                    if let Err(e) = handle_command(&rt, &msg.text).await {
                        tracing::warn!("telegram command error: {e}");
                        let _ = rt
                            .telegram
                            .send_text(&format!("⚠️ <code>{e}</code>"))
                            .await;
                    }
                }
            }
            Err(e) => {
                if e.contains("429") || e.contains("Flood") {
                    flood.on_rate_limited(now_ms());
                }
                tracing::debug!("telegram poll: {e}");
                tokio::time::sleep(std::time::Duration::from_millis(flood.wait_ms())).await;
            }
        }
    }
}

async fn handle_command(rt: &SharedRuntime, raw: &str) -> Result<(), String> {
    let text = raw.trim();
    let lower = text.to_lowercase();
    let cmd = lower.split_whitespace().next().unwrap_or("");

    let reply = match cmd {
        "/start" | "/help" | "help" | "مساعدة" => HELP_AR.to_string(),
        "/status" | "/رصيد" | "رصيد" | "status" | "حالة" => format_status(rt).await,
        "/price" | "سعر" => format_price(rt, text).await,
        "/pause" | "/stop" | "إيقاف" => {
            if rt.bot_is_running() {
                rt.set_bot_running(false);
                crate::telegram_notify::system_status(rt, false).await;
            }
            "⏸ تم إيقاف البوت (Telegram → Terminal)".into()
        }
        "/resume" | "/play" | "تشغيل" => {
            if !rt.bot_is_running() {
                rt.set_bot_running(true);
                crate::telegram_notify::system_status(rt, true).await;
            }
            "▶️ تم تشغيل البوت (Telegram → Terminal)".into()
        }
        "/toggle" => {
            let v = control_actions::toggle_bot(rt).await;
            format!(
                "🔄 حالة البوت: <code>{}</code>",
                if v.get("bot_running").and_then(|x| x.as_bool()).unwrap_or(false) {
                    "نشط"
                } else {
                    "متوقف"
                }
            )
        }
        "/buy" | "/enter" | "/دخول" | "دخول" => {
            let sym = parse_symbol_arg(text).unwrap_or_else(|| rt.settings.symbol.clone());
            let (code, body) = control_actions::paper_enter(rt, &sym, 2.0, "telegram").await;
            if code.is_success() {
                format!("🟢 Paper دخول <code>{sym}</code> @ سعر Binance الحي")
            } else {
                body.get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("enter_failed")
                    .to_string()
            }
        }
        "/close_win" | "رابحة" => {
            let (_, body) = control_actions::close_winners(rt, "telegram").await;
            format!(
                "💰 إغلاق الرابحة — أغلقت <code>{}</code> (Terminal sync)",
                body.get("closed").and_then(|v| v.as_u64()).unwrap_or(0)
            )
        }
        "/close_loss" | "خاسرة" => {
            let (_, body) = control_actions::close_losers(rt, "telegram").await;
            format!(
                "📉 إغلاق الخاسرة — أغلقت <code>{}</code>",
                body.get("closed").and_then(|v| v.as_u64()).unwrap_or(0)
            )
        }
        "/emergency" | "/close_all" | "إغلاق_الكل" | "إغلاق الكل" => {
            let (_, body) = control_actions::emergency_close_all(rt, "telegram").await;
            format!(
                "🚨 إغلاق طوارئ — <code>{}</code> صفقة",
                body.get("closed").and_then(|v| v.as_u64()).unwrap_or(0)
            )
        }
        _ if lower.starts_with("/buy ") => {
            let sym = parse_symbol_arg(text).unwrap_or_else(|| "BTCUSDT".into());
            let (code, body) = control_actions::paper_enter(rt, &sym, 2.0, "telegram").await;
            if code.is_success() {
                format!("🟢 Paper دخول <code>{sym}</code>")
            } else {
                body.get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("enter_failed")
                    .into()
            }
        }
        _ => {
            return Ok(());
        }
    };

    rt.telegram.send_text(&reply).await?;
    Ok(())
}

async fn format_status(rt: &SharedRuntime) -> String {
    let s = control_actions::status_snapshot(rt).await;
    format!(
        "📊 <b>صقر — Terminal Mirror</b>\n\
mode: <code>{}</code>\n\
سوق: <code>{}</code> @ <code>{:.2}</code>\n\
رصيد Paper: <code>{:.2} $</code>\n\
اليوم: <code>{:+.2}%</code>\n\
مفتوحة: <code>{}</code> | +<code>{:.2}</code> / -<code>{:.2}</code> $\n\
بوت: <code>{}</code>",
        s.get("mode").and_then(|v| v.as_str()).unwrap_or("?"),
        s.get("symbol").and_then(|v| v.as_str()).unwrap_or("BTCUSDT"),
        s.get("market_price").and_then(|v| v.as_f64()).unwrap_or(0.0),
        s.get("balance_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
        s.get("daily_pct").and_then(|v| v.as_f64()).unwrap_or(0.0),
        s.get("open_positions").and_then(|v| v.as_u64()).unwrap_or(0),
        s.get("winning_pnl_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
        s.get("losing_pnl_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
        if s.get("bot_running").and_then(|v| v.as_bool()).unwrap_or(true) {
            "نشط ✅"
        } else {
            "متوقف ⏸"
        },
    )
}

async fn format_price(rt: &SharedRuntime, text: &str) -> String {
    let sym = parse_symbol_arg(text).unwrap_or_else(|| rt.settings.symbol.clone());
    match rt.market.price(&sym).await {
        Ok(px) => format!(
            "📡 <code>{sym}</code> = <code>{px:.4}</code>\nمصدر: <code>{}</code>",
            rt.settings.market_rest_url
        ),
        Err(e) => format!("⚠️ سعر {sym}: <code>{e}</code>"),
    }
}

fn parse_symbol_arg(text: &str) -> Option<String> {
    let parts: Vec<&str> = text.split_whitespace().collect();
    if parts.len() < 2 {
        return None;
    }
    let sym = parts[1].to_uppercase().replace('/', "");
    if sym.ends_with("USDT") {
        Some(sym)
    } else {
        Some(format!("{sym}USDT"))
    }
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}
