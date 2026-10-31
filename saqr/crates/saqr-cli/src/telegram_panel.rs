use std::sync::Arc;

use serde_json::json;

use crate::control_actions;
use crate::market_signals;
use crate::runtime::SharedRuntime;

/// Main control board (summary + action buttons only).
pub async fn push_dashboard(rt: &SharedRuntime) -> Result<(), String> {
    let mid = *rt.telegram_board_message_id.lock();
    push_main_board(rt, mid).await
}

async fn push_main_board(rt: &SharedRuntime, message_id: Option<i64>) -> Result<(), String> {
    let active = rt.telegram_panel_active_section.lock().clone();
    let text = build_home_summary(rt).await?;
    let keyboard = build_main_keyboard(rt, &active);

    if let Some(mid) = message_id {
        *rt.telegram_board_message_id.lock() = Some(mid);
        return rt.telegram.edit_dashboard(mid, &text, &keyboard).await;
    }

    let existing_mid = *rt.telegram_board_message_id.lock();
    if let Some(mid) = existing_mid {
        if rt.telegram.edit_dashboard(mid, &text, &keyboard).await.is_ok() {
            return Ok(());
        }
        *rt.telegram_board_message_id.lock() = None;
    }
    let mid = rt.telegram.send_dashboard(&text, &keyboard).await?;
    *rt.telegram_board_message_id.lock() = Some(mid);
    Ok(())
}

/// Section content in its own Telegram message (edited in place per section).
async fn push_section_panel(rt: &SharedRuntime, section: &str) -> Result<(), String> {
    let text = build_section_body(rt, section).await?;
    let keyboard = json!({
        "inline_keyboard": [[
            {"text": "🔄 تحديث", "callback_data": format!("view:{section}")},
            {"text": "🏠 لوحة الرئيسية", "callback_data": "view:home"}
        ]]
    });

    let section_mid = rt.telegram_section_messages.lock().get(section).copied();
    if let Some(mid) = section_mid {
        if rt.telegram.edit_dashboard(mid, &text, &keyboard).await.is_ok() {
            return Ok(());
        }
        rt.telegram_section_messages.lock().remove(section);
    }

    let mid = rt.telegram.send_dashboard(&text, &keyboard).await?;
    rt.telegram_section_messages.lock().insert(section.to_string(), mid);
    Ok(())
}

async fn refresh_open_sections(rt: &SharedRuntime) {
    let keys: Vec<String> = rt.telegram_section_messages.lock().keys().cloned().collect();
    for section in keys {
        if let Err(e) = push_section_panel(rt, &section).await {
            tracing::debug!("section refresh {section}: {e}");
        }
    }
}

pub async fn handle_callback(
    rt: &SharedRuntime,
    query_id: &str,
    data: &str,
    main_message_id: Option<i64>,
) -> Result<(), String> {
    let toast = match data {
        "act:close_win" => {
            let (_, b) = control_actions::close_winners(rt, "telegram").await;
            format!(
                "💰 أغلقت {} رابحة",
                b.get("closed").and_then(|v| v.as_u64()).unwrap_or(0)
            )
        }
        "act:close_loss" => {
            let (_, b) = control_actions::close_losers(rt, "telegram").await;
            format!(
                "📉 أغلقت {} خاسرة",
                b.get("closed").and_then(|v| v.as_u64()).unwrap_or(0)
            )
        }
        "act:emergency" => {
            let (_, b) = control_actions::emergency_close_all(rt, "telegram").await;
            format!(
                "🚨 طوارئ: {}",
                b.get("closed").and_then(|v| v.as_u64()).unwrap_or(0)
            )
        }
        "act:toggle" => {
            let v = control_actions::toggle_bot(rt).await;
            if v.get("bot_running").and_then(|x| x.as_bool()).unwrap_or(true) {
                "▶️ البوت نشط".into()
            } else {
                "⏸ متوقف".into()
            }
        }
        "act:buy_btc" => {
            let sym = rt.settings.symbol.clone();
            let (code, body) = control_actions::enter_market(rt, &sym, 2.0, "telegram").await;
            if code.is_success() {
                format!("🟢 دخول {sym}")
            } else {
                body.get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("فشل")
                    .to_string()
            }
        }
        "act:refresh" => {
            refresh_open_sections(rt).await;
            "🔄 تم".into()
        }
        s if s.starts_with("view:") => {
            let view = s.strip_prefix("view:").unwrap_or("home");
            *rt.telegram_panel_active_section.lock() = view.to_string();
            if view == "home" {
                "🏠 اللوحة الرئيسية".into()
            } else {
                push_section_panel(rt, view).await?;
                match view {
                    "signals" => "📊 فُتحت الإشارات في رسالة منفصلة".into(),
                    "positions" => "📂 فُتحت المراكز".into(),
                    "liquidity" => "🔥 فُتحت السيولة".into(),
                    "report" => "📋 فُتح التقرير".into(),
                    "history" => "🕐 فُتح السجل".into(),
                    _ => "✓".into(),
                }
            }
        }
        _ => "—".into(),
    };

    let _ = rt.telegram.answer_callback(query_id, Some(&toast)).await;
    push_main_board(rt, main_message_id).await?;
    Ok(())
}

async fn build_home_summary(rt: &SharedRuntime) -> Result<String, String> {
    let mirror = rt.refresh_mirror().await;
    let clock = tactical_clock_utc3();
    let bot = if rt.bot_is_running() { "🟢 ONLINE" } else { "⏸ PAUSED" };
    let mode = if rt.settings.is_paper_trading() {
        "Paper"
    } else if rt.settings.is_testnet_execution() {
        "Testnet"
    } else {
        "LIVE"
    };

    Ok(format!(
        "<b>🦅 SAQR · لوحة التحكم</b>  <code>v6.2.3</code>\n\
<code>{mode}</code> · Binance ⇄ Telegram\n\n\
<b>الرصيد الإجمالي</b>\n\
<code>{bal} USDT</code>\n\n\
<b>أرباح اليوم</b>\n\
<code>{day:+.2}%</code>\n\n\
<b>الصفقات المفتوحة</b>  <code>{open}</code>\n\
<b>رابحة</b> <code>+{win:.2}</code>  ·  <b>خاسرة</b> <code>-{lose:.2}</code>\n\n\
<b>السيرفر</b> <code>{clock}</code>  ·  {bot}\n\n\
<i>📌 الإشارات والمراكز تظهر في <b>رسالة منفصلة</b> عند الضغط على القسم</i>",
        bal = fmt_money(mirror.total_balance_usd),
        day = mirror.daily_profit_pct,
        open = mirror.open_positions_count,
        win = mirror.winning_pnl_usd,
        lose = mirror.losing_pnl_usd,
    ))
}

async fn build_section_body(rt: &SharedRuntime, section: &str) -> Result<String, String> {
    let mirror = rt.refresh_mirror().await;
    match section {
        "signals" => {
            let mut out = String::from(
                "<b>📊 الإشارات الفنية</b>\n\
<code>Binance · 15m · 7 أزواج</code>\n\
────────────────\n",
            );
            let signals = market_signals::fetch_live_signals(rt, "15m").await;
            if signals.is_empty() {
                out.push_str("<i>لا بيانات — تحقق الاتصال</i>\n");
            }
            for s in signals {
                let side = if s.direction == "BUY" {
                    "🟢 BUY"
                } else {
                    "🔴 SELL"
                };
                out.push_str(&format!(
                    "<b>{}</b>\n  {side} · <code>{:.4}</code>\n  قوة <code>{}%</code> · RSI <code>{:.0}</code>\n\n",
                    s.pair, s.price, s.strength, s.rsi
                ));
            }
            Ok(out)
        }
        "positions" => {
            let mut out = String::from(
                "<b>📂 مراكزي المفتوحة</b>\n\
────────────────\n",
            );
            if mirror.positions.is_empty() {
                out.push_str("<i>لا توجد مراكز مفتوحة</i>\n");
            }
            for p in &mirror.positions {
                out.push_str(&format!(
                    "<b>{}</b>\n  lot <code>{}</code>\n  دخول <code>{:.4}</code> · الآن <code>{:.4}</code>\n  PnL <code>{:+.2} USDT</code>\n\n",
                    p.pair, p.lot, p.entry, p.current, p.pnl
                ));
            }
            Ok(out)
        }
        "liquidity" => {
            let mut out = String::from(
                "<b>🔥 الأعلى سيولة</b>\n\
<code>حجم 24h (مليار USDT)</code>\n\
────────────────\n",
            );
            match rt.market.tickers_24h().await {
                Ok(all) => {
                    for sym in market_signals::watch_symbols(rt) {
                        if let Some(t) = all.iter().find(|x| x.symbol == sym) {
                            let vol: f64 = t.quote_volume.parse().unwrap_or(0.0) / 1e9;
                            let base = sym.strip_suffix("USDT").unwrap_or(sym.as_str());
                            out.push_str(&format!(
                                "<b>{base}/USDT</b>  <code>{vol:.2}B</code>\n"
                            ));
                        }
                    }
                }
                Err(e) => out.push_str(&format!("<i>{e}</i>\n")),
            }
            Ok(out)
        }
        "report" => {
            let mut out = String::from(
                "<b>📋 التقارير</b>\n\
────────────────\n",
            );
            if rt.settings.is_paper_trading() {
                let r = rt.paper.report("daily");
                out.push_str(&format!(
                    "رصيد: <code>{:.2}</code>\nفوز: <code>{}</code> · خسارة: <code>{}</code>\n",
                    mirror.total_balance_usd,
                    r.get("win_count").and_then(|v| v.as_u64()).unwrap_or(0),
                    r.get("loss_count").and_then(|v| v.as_u64()).unwrap_or(0),
                ));
            } else {
                out.push_str(&format!(
                    "رصيد إجمالي: <code>{:.2}</code>\nUSDT حر: <code>{:.2}</code>\nUSDT مقفل: <code>{:.2}</code>\n",
                    mirror.total_balance_usd, mirror.usdt_free, mirror.usdt_locked
                ));
            }
            Ok(out)
        }
        "history" => {
            let mut out = String::from(
                "<b>🕐 سجل الصفقات</b>\n\
────────────────\n",
            );
            if rt.settings.is_paper_trading() {
                let rows = rt.paper.history();
                if rows.is_empty() {
                    out.push_str("<i>لا سجل بعد</i>\n");
                }
                for t in rows.iter().rev().take(12) {
                    out.push_str(&format!(
                        "<code>{}</code>  PnL <code>{:+.2}</code>\n",
                        t.pair, t.pnl_usd
                    ));
                }
            } else {
                let sym = rt.settings.symbol.clone();
                match rt.binance.my_trades(&sym, None).await {
                    Ok(rows) if rows.is_empty() => out.push_str("<i>لا صفقات Testnet بعد</i>\n"),
                    Ok(rows) => {
                        for t in rows.iter().rev().take(12) {
                            let side = if t.isBuyer { "BUY" } else { "SELL" };
                            out.push_str(&format!(
                                "<code>{sym}</code> {side} @ <code>{}</code>\n",
                                t.price
                            ));
                        }
                    }
                    Err(e) => out.push_str(&format!("<i>{e}</i>\n")),
                }
            }
            Ok(out)
        }
        _ => Ok("<b>قسم غير معروف</b>".into()),
    }
}

fn build_main_keyboard(rt: &SharedRuntime, active: &str) -> serde_json::Value {
    let pause = if rt.bot_is_running() {
        "⏸ إيقاف مؤقت"
    } else {
        "▶️ تشغيل"
    };
    let tag = |key: &str, label: &str| {
        if active == key {
            format!("• {label}")
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
            [{"text": "🚨 إغلاق طوارئ للكل", "callback_data": "act:emergency"}],
            [
                {"text": tag("signals", "📊 الإشارات"), "callback_data": "view:signals"},
                {"text": tag("positions", "📂 المراكز"), "callback_data": "view:positions"}
            ],
            [
                {"text": tag("liquidity", "🔥 السيولة"), "callback_data": "view:liquidity"},
                {"text": tag("report", "📋 التقارير"), "callback_data": "view:report"}
            ],
            [
                {"text": tag("history", "🕐 السجل"), "callback_data": "view:history"},
                {"text": "🔄 تحديث الكل", "callback_data": "act:refresh"}
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
    format!("{}.{}", with_commas.chars().rev().collect::<String>(), frac)
}

fn tactical_clock_utc3() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
        + 3 * 3600;
    format!(
        "{:02}:{:02}:{:02}",
        (secs / 3600) % 24,
        (secs / 60) % 60,
        secs % 60
    )
}

pub fn spawn_panel_refresh(rt: Arc<SharedRuntime>) {
    tokio::spawn(async move {
        let _ = push_dashboard(&rt).await;
        let secs = rt.settings.signal_interval_secs.max(3);
        let mut tick = tokio::time::interval(std::time::Duration::from_secs(secs));
        loop {
            tick.tick().await;
            if let Err(e) = push_dashboard(&rt).await {
                tracing::debug!("main board: {e}");
            }
            refresh_open_sections(&rt).await;
        }
    });
}

// Legacy name used by /panel
pub async fn push_dashboard_message(rt: &SharedRuntime, message_id: Option<i64>) -> Result<(), String> {
    push_main_board(rt, message_id).await
}
