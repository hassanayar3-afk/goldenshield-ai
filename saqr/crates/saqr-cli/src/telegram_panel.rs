use std::sync::Arc;

use serde_json::json;

use crate::control_actions;
use crate::market_signals;
use crate::runtime::SharedRuntime;

pub async fn push_dashboard(rt: &SharedRuntime) -> Result<(), String> {
    let section = rt.telegram_panel_section.lock().clone();
    let text = build_dashboard_text(rt, &section).await?;
    let keyboard = build_dashboard_keyboard(rt, &section);
    let mid = *rt.telegram_board_message_id.lock();
    if let Some(mid) = mid {
        if rt.telegram.edit_dashboard(mid, &text, &keyboard).await.is_err() {
            *rt.telegram_board_message_id.lock() = None;
        } else {
            return Ok(());
        }
    }
    match rt.telegram.send_dashboard(&text, &keyboard).await {
        Ok(mid) => {
            *rt.telegram_board_message_id.lock() = Some(mid);
            Ok(())
        }
        Err(e) => Err(e),
    }
}

pub async fn handle_callback(rt: &SharedRuntime, query_id: &str, data: &str) -> Result<(), String> {
    let toast = match data {
        "act:close_win" => {
            let (_, b) = control_actions::close_winners(rt, "telegram").await;
            format!("إغلاق الرابحة: {}", b.get("closed").and_then(|v| v.as_u64()).unwrap_or(0))
        }
        "act:close_loss" => {
            let (_, b) = control_actions::close_losers(rt, "telegram").await;
            format!("إغلاق الخاسرة: {}", b.get("closed").and_then(|v| v.as_u64()).unwrap_or(0))
        }
        "act:emergency" => {
            let (_, b) = control_actions::emergency_close_all(rt, "telegram").await;
            format!("طوارئ: {}", b.get("closed").and_then(|v| v.as_u64()).unwrap_or(0))
        }
        "act:toggle" => {
            let v = control_actions::toggle_bot(rt).await;
            if v.get("bot_running").and_then(|x| x.as_bool()).unwrap_or(true) {
                "▶️ البوت نشط".into()
            } else {
                "⏸ البوت متوقف".into()
            }
        }
        "act:buy_btc" => {
            let sym = rt.settings.symbol.clone();
            let (code, body) = control_actions::paper_enter(rt, &sym, 2.0, "telegram").await;
            if code.is_success() {
                format!("🟢 دخول {sym}")
            } else {
                body.get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("فشل")
                    .to_string()
            }
        }
        s if s.starts_with("view:") => {
            let view = s.strip_prefix("view:").unwrap_or("home");
            *rt.telegram_panel_section.lock() = view.to_string();
            match view {
                "signals" => "📊 الإشارات الفنية",
                "positions" => "📂 مراكزي المفتوحة",
                "liquidity" => "🔥 الأعلى سيولة",
                "report" => "📋 التقارير",
                "history" => "🕐 سجل الصفقات",
                _ => "🏠 الرئيسية",
            }
            .to_string()
        }
        _ => "—".into(),
    };
    let _ = rt.telegram.answer_callback(query_id, Some(&toast)).await;
    push_dashboard(rt).await?;
    Ok(())
}

async fn build_dashboard_text(rt: &SharedRuntime, section: &str) -> Result<String, String> {
    let mirror = rt.refresh_mirror().await;
    let clock = tactical_clock_utc3();
    let bot = if rt.bot_is_running() {
        "🟢 ONLINE"
    } else {
        "⏸ PAUSED"
    };

    let mut out = format!(
        "🦅 <b>GoldenShield — صقر v6.2.3</b>\n\
┏━━━━━━━━━━━━━━━━━━━━━━┓\n\
💎 <b>الرصيد الإجمالي</b>\n\
   <code>{bal} $</code>\n\
📈 <b>أرباح اليوم</b>  <code>{day:+.2}%</code>\n\
┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n\
📊 <b>الصفقات المفتوحة حالياً</b>  <code>{open}</code>\n\
┌──────────────┬──────────────┐\n\
│ 🟢 رابحة     │ 🔴 خاسرة     │\n\
│ <code>+{win:.2} $</code> │ <code>-{lose:.2} $</code> │\n\
└──────────────┴──────────────┘\n\
🕐 <b>زمن السيرفر التكتيكي</b> <code>{clock}</code> · {bot}\n\
━━━━━━━━━━━━━━━━━━━━━━━━━━\n",
        bal = fmt_money(mirror.total_balance_usd),
        day = mirror.daily_profit_pct,
        open = mirror.open_positions_count,
        win = mirror.winning_pnl_usd,
        lose = mirror.losing_pnl_usd,
    );

    match section {
        "signals" => {
            out.push_str("<b>📊 الإشارات الفنية</b> (Binance 15m)\n");
            let signals = market_signals::fetch_live_signals(rt, "15m").await;
            if signals.is_empty() {
                out.push_str("<i>جاري الاتصال بالسوق…</i>\n");
            }
            for s in signals.iter().take(10) {
                let tag = if s.direction == "BUY" { "🟢 شراء" } else { "🔴 بيع" };
                out.push_str(&format!(
                    "• <code>{}</code> {tag} · <code>{:.2}</code> · {}% · RSI {}\n",
                    s.pair, s.price, s.strength, s.rsi as i32
                ));
            }
        }
        "positions" => {
            out.push_str("<b>📂 مراكزي المفتوحة</b>\n");
            if mirror.positions.is_empty() {
                out.push_str("<i>لا توجد صفقات مفتوحة</i>\n");
            }
            for p in &mirror.positions {
                out.push_str(&format!(
                    "• <code>{}</code> {} · دخول <code>{:.4}</code> · PnL <code>{:+.2} $</code>\n",
                    p.pair, p.lot, p.entry, p.pnl
                ));
            }
        }
        "liquidity" => {
            out.push_str("<b>🔥 الأعلى سيولة</b>\n");
            match rt.market.tickers_24h().await {
                Ok(all) => {
                    for sym in market_signals::watch_symbols(rt) {
                        if let Some(t) = all.iter().find(|x| x.symbol == sym) {
                            let vol: f64 = t.quote_volume.parse().unwrap_or(0.0) / 1e9;
                            let base = sym.strip_suffix("USDT").unwrap_or(sym.as_str());
                            out.push_str(&format!(
                                "• <code>{base}/USDT</code> · <code>{vol:.1}B</code>\n"
                            ));
                        }
                    }
                }
                Err(e) => out.push_str(&format!("<i>{e}</i>\n")),
            }
        }
        "report" => {
            let r = rt.paper.report("daily");
            out.push_str("<b>📋 تقرير اليوم</b>\n");
            out.push_str(&format!(
                "رصيد: <code>{:.2} $</code>\nفوز: <code>{}</code> · خسارة: <code>{}</code>\n",
                mirror.total_balance_usd,
                r.get("win_count").and_then(|v| v.as_u64()).unwrap_or(0),
                r.get("loss_count").and_then(|v| v.as_u64()).unwrap_or(0),
            ));
        }
        "history" => {
            out.push_str("<b>🕐 سجل الصفقات</b>\n");
            let rows = rt.paper.history();
            if rows.is_empty() {
                out.push_str("<i>لا يوجد سجل بعد</i>\n");
            }
            for t in rows.iter().rev().take(8) {
                out.push_str(&format!(
                    "• <code>{}</code> PnL <code>{:+.2} $</code>\n",
                    t.pair, t.pnl_usd
                ));
            }
        }
        _ => {
            out.push_str("<b>🎛 لوحة التحكم</b> — اختر قسماً من الأزرار ↓\n");
            let exec = if rt.settings.is_paper_trading() {
                "Paper Sandbox"
            } else if rt.settings.is_testnet_execution() {
                "Binance Spot Testnet (أوامر حقيقية)"
            } else {
                "Binance Spot LIVE"
            };
            out.push_str(&format!(
                "<i>تحديث كل {}ث · {exec}</i>\n",
                rt.settings.signal_interval_secs
            ));
        }
    }

    Ok(out)
}

fn build_dashboard_keyboard(rt: &SharedRuntime, section: &str) -> serde_json::Value {
    let pause = if rt.bot_is_running() {
        "⏸ إيقاف مؤقت"
    } else {
        "▶️ تشغيل البوت"
    };
    let mk = |key: &str, label: &str| {
        if section == key {
            format!("▸ {label}")
        } else {
            label.to_string()
        }
    };
    json!({
        "inline_keyboard": [
            [
                {"text": "💰 إغلاق الرابحة", "callback_data": "act:close_win"},
                {"text": "📉 إغلاق الخاسرة", "callback_data": "act:close_loss"}
            ],
            [
                {"text": pause, "callback_data": "act:toggle"},
                {"text": "🟢 دخول BTC", "callback_data": "act:buy_btc"}
            ],
            [
                {"text": "🚨 إغلاق طوارئ — الكل", "callback_data": "act:emergency"}
            ],
            [
                {"text": mk("signals", "📊 إشارات"), "callback_data": "view:signals"},
                {"text": mk("positions", "📂 مراكز"), "callback_data": "view:positions"}
            ],
            [
                {"text": mk("liquidity", "🔥 سيولة"), "callback_data": "view:liquidity"},
                {"text": mk("report", "📋 تقارير"), "callback_data": "view:report"}
            ],
            [
                {"text": mk("history", "🕐 السجل"), "callback_data": "view:history"},
                {"text": mk("home", "🏠 الرئيسية"), "callback_data": "view:home"}
            ]
        ]
    })
}

fn fmt_money(n: f64) -> String {
    let s = format!("{n:.2}");
    let parts: Vec<&str> = s.split('.').collect();
    let intp = parts.first().copied().unwrap_or("0");
    let frac = parts.get(1).copied().unwrap_or("00");
    let mut with_commas = String::new();
    for (i, c) in intp.chars().rev().enumerate() {
        if i > 0 && i % 3 == 0 {
            with_commas.push(',');
        }
        with_commas.push(c);
    }
    let int_fmt: String = with_commas.chars().rev().collect();
    format!("{int_fmt}.{frac}")
}

fn tactical_clock_utc3() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
        + 3 * 3600;
    let h = (secs / 3600) % 24;
    let m = (secs / 60) % 60;
    let s = secs % 60;
    format!("{h:02}:{m:02}:{s:02}")
}

pub fn spawn_panel_refresh(rt: Arc<SharedRuntime>) {
    tokio::spawn(async move {
        let secs = rt.settings.signal_interval_secs.max(2);
        let mut tick = tokio::time::interval(std::time::Duration::from_secs(secs));
        tick.tick().await;
        loop {
            tick.tick().await;
            if let Err(e) = push_dashboard(&rt).await {
                tracing::debug!("telegram panel refresh: {e}");
            }
        }
    });
}
