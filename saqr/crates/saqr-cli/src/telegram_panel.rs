use std::sync::Arc;

use serde_json::json;

use crate::control_actions;
use crate::market_signals;
use crate::runtime::SharedRuntime;

pub async fn push_dashboard(rt: &SharedRuntime) -> Result<(), String> {
    let mid = *rt.telegram_board_message_id.lock();
    push_dashboard_message(rt, mid).await
}

pub async fn push_dashboard_message(rt: &SharedRuntime, message_id: Option<i64>) -> Result<(), String> {
    let section = rt.telegram_panel_section.lock().clone();
    let text = build_dashboard_text(rt, &section).await?;
    let keyboard = build_dashboard_keyboard(rt, &section);

    if let Some(mid) = message_id {
        *rt.telegram_board_message_id.lock() = Some(mid);
        rt.telegram.edit_dashboard(mid, &text, &keyboard).await?;
        return Ok(());
    }

    let mid = *rt.telegram_board_message_id.lock();
    if let Some(mid) = mid {
        if rt.telegram.edit_dashboard(mid, &text, &keyboard).await.is_ok() {
            return Ok(());
        }
        *rt.telegram_board_message_id.lock() = None;
    }
    match rt.telegram.send_dashboard(&text, &keyboard).await {
        Ok(mid) => {
            *rt.telegram_board_message_id.lock() = Some(mid);
            Ok(())
        }
        Err(e) => Err(e),
    }
}

pub async fn handle_callback(
    rt: &SharedRuntime,
    query_id: &str,
    data: &str,
    message_id: Option<i64>,
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
                "🚨 طوارئ: {} صفقة",
                b.get("closed").and_then(|v| v.as_u64()).unwrap_or(0)
            )
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
            let (code, body) = control_actions::enter_market(rt, &sym, 2.0, "telegram").await;
            if code.is_success() {
                format!("🟢 دخول {sym}")
            } else {
                body.get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("فشل الدخول")
                    .to_string()
            }
        }
        "act:refresh" => "🔄 تحديث".into(),
        s if s.starts_with("view:") => {
            let view = s.strip_prefix("view:").unwrap_or("home");
            *rt.telegram_panel_section.lock() = view.to_string();
            match view {
                "signals" => "📊 الإشارات",
                "positions" => "📂 المراكز",
                "liquidity" => "🔥 السيولة",
                "report" => "📋 التقارير",
                "history" => "🕐 السجل",
                "calc" => "🧮 الحاسبة (استخدم /price)",
                _ => "🏠 الرئيسية",
            }
            .to_string()
        }
        _ => "زر غير معروف".into(),
    };

    let _ = rt.telegram.answer_callback(query_id, Some(&toast)).await;
    push_dashboard_message(rt, message_id).await?;
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
    let mode_label = if rt.settings.is_paper_trading() {
        "Paper"
    } else if rt.settings.is_testnet_execution() {
        "Testnet ✅"
    } else {
        "LIVE ⚠️"
    };

    let mut out = format!(
        "🦅 <b>GoldenShield — صقر v6.2.3</b> · <code>{mode_label}</code>\n\
┏━━━━━━━━━━━━━━━━━━━━━━┓\n\
💎 <b>الرصيد الإجمالي</b>  <code>{bal} $</code>\n\
📈 <b>أرباح اليوم</b>  <code>{day:+.2}%</code>\n\
┗━━━━━━━━━━━━━━━━━━━━━━┛\n\
📊 <b>صفقات مفتوحة</b> <code>{open}</code>\n\
🟢 رابحة <code>+{win:.2} $</code> · 🔴 خاسرة <code>-{lose:.2} $</code>\n\
🕐 <code>{clock}</code> · {bot}\n\
━━━━━━━━━━━━━━━━━━━━━━━━━━\n",
        bal = fmt_money(mirror.total_balance_usd),
        day = mirror.daily_profit_pct,
        open = mirror.open_positions_count,
        win = mirror.winning_pnl_usd,
        lose = mirror.losing_pnl_usd,
    );

    match section {
        "signals" => {
            out.push_str("<b>📊 الإشارات الفنية</b> (15m · Binance)\n");
            let signals = market_signals::fetch_live_signals(rt, "15m").await;
            if signals.is_empty() {
                out.push_str("<i>لا بيانات — تحقق REST/Testnet</i>\n");
            }
            for s in signals.iter().take(10) {
                let tag = if s.direction == "BUY" { "🟢" } else { "🔴" };
                out.push_str(&format!(
                    "{tag} <code>{}</code> · <code>{:.4}</code> · {}% RSI{}\n",
                    s.pair, s.price, s.strength, s.rsi as i32
                ));
            }
        }
        "positions" => {
            out.push_str("<b>📂 مراكزي المفتوحة</b>\n");
            if mirror.positions.is_empty() {
                out.push_str("<i>لا مراكز — جرّب «دخول BTC»</i>\n");
            }
            for p in &mirror.positions {
                out.push_str(&format!(
                    "• <code>{}</code> lot <code>{}</code> · PnL <code>{:+.2}$</code>\n",
                    p.pair, p.lot, p.pnl
                ));
            }
        }
        "liquidity" => {
            out.push_str("<b>🔥 الأعلى سيولة (24h)</b>\n");
            match rt.market.tickers_24h().await {
                Ok(all) => {
                    for sym in market_signals::watch_symbols(rt) {
                        if let Some(t) = all.iter().find(|x| x.symbol == sym) {
                            let vol: f64 = t.quote_volume.parse().unwrap_or(0.0) / 1e9;
                            let base = sym.strip_suffix("USDT").unwrap_or(sym.as_str());
                            out.push_str(&format!(
                                "• <code>{base}/USDT</code> <code>{vol:.1}B</code>\n"
                            ));
                        }
                    }
                }
                Err(e) => out.push_str(&format!("<i>{e}</i>\n")),
            }
        }
        "report" => {
            out.push_str("<b>📋 تقارير اليوم</b>\n");
            if rt.settings.is_paper_trading() {
                let r = rt.paper.report("daily");
                out.push_str(&format!(
                    "فوز: <code>{}</code> · خسارة: <code>{}</code>\n",
                    r.get("win_count").and_then(|v| v.as_u64()).unwrap_or(0),
                    r.get("loss_count").and_then(|v| v.as_u64()).unwrap_or(0),
                ));
            } else {
                out.push_str(&format!(
                    "USDT free: <code>{:.2}</code> · locked: <code>{:.2}</code>\n",
                    mirror.usdt_free, mirror.usdt_locked
                ));
            }
        }
        "history" => {
            out.push_str("<b>🕐 سجل الصفقات</b>\n");
            if rt.settings.is_paper_trading() {
                let rows = rt.paper.history();
                if rows.is_empty() {
                    out.push_str("<i>لا سجل Paper بعد</i>\n");
                }
                for t in rows.iter().rev().take(8) {
                    out.push_str(&format!(
                        "• <code>{}</code> <code>{:+.2}$</code>\n",
                        t.pair, t.pnl_usd
                    ));
                }
            } else {
                let sym = rt.settings.symbol.clone();
                match rt.binance.my_trades(&sym, None).await {
                    Ok(rows) if rows.is_empty() => out.push_str("<i>لا trades على Testnet بعد</i>\n"),
                    Ok(rows) => {
                        for t in rows.iter().rev().take(8) {
                            let side = if t.isBuyer { "BUY" } else { "SELL" };
                            out.push_str(&format!(
                                "• <code>{sym}</code> {side} <code>{}</code>\n",
                                t.price
                            ));
                        }
                    }
                    Err(e) => out.push_str(&format!("<i>{e}</i>\n")),
                }
            }
        }
        "calc" => {
            out.push_str("<b>🧮 حاسبة العقود</b>\n");
            out.push_str("أرسل: <code>/price ETHUSDT</code>\n");
            out.push_str("دخول 2%: زر «دخول BTC» أو <code>/buy SOLUSDT</code>\n");
        }
        _ => {
            out.push_str("<b>🎛 اضغط زراً بالأسفل</b>\n");
            out.push_str(&format!(
                "<i>تحديث كل {}ث · {} · الأزرار على <b>آخر لوحة</b></i>\n",
                rt.settings.signal_interval_secs, mode_label
            ));
        }
    }

    Ok(out)
}

fn build_dashboard_keyboard(rt: &SharedRuntime, section: &str) -> serde_json::Value {
    let pause = if rt.bot_is_running() {
        "⏸ إيقاف"
    } else {
        "▶️ تشغيل"
    };
    let mk = |key: &str, label: &str| {
        if section == key {
            format!("▸{label}")
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
                {"text": "🚨 إغلاق طوارئ", "callback_data": "act:emergency"},
                {"text": "🔄", "callback_data": "act:refresh"}
            ],
            [
                {"text": mk("signals", "📊إشارات"), "callback_data": "view:signals"},
                {"text": mk("positions", "📂مراكز"), "callback_data": "view:positions"}
            ],
            [
                {"text": mk("liquidity", "🔥سيولة"), "callback_data": "view:liquidity"},
                {"text": mk("report", "📋تقارير"), "callback_data": "view:report"}
            ],
            [
                {"text": mk("history", "🕐سجل"), "callback_data": "view:history"},
                {"text": mk("home", "🏠رئيسية"), "callback_data": "view:home"}
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
        let _ = push_dashboard(&rt).await;
        let secs = rt.settings.signal_interval_secs.max(2);
        let mut tick = tokio::time::interval(std::time::Duration::from_secs(secs));
        loop {
            tick.tick().await;
            if let Err(e) = push_dashboard(&rt).await {
                tracing::debug!("telegram panel refresh: {e}");
            }
        }
    });
}
