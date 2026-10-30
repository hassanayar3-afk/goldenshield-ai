use saqr_core::binance::mirror::MirrorPosition;
use saqr_core::binance::signed_api::OrderResponse;

use crate::runtime::SharedRuntime;

pub async fn system_status(rt: &SharedRuntime, running: bool) {
    if !rt.telegram.is_configured() {
        return;
    }
    let state = if running { "نشط ✅" } else { "متوقف مؤقتاً ⏸" };
    let text = format!("🦅 <b>صقر SAQR</b>\nحالة النظام: {state}\nmode: <code>{}</code>", rt.settings.mode);
    let _ = rt.telegram.send_text(&text).await;
}

pub async fn trade_entry(
    rt: &SharedRuntime,
    pair: &str,
    side: &str,
    entry: f64,
    stop: f64,
    target: f64,
    qty: &str,
) {
    if !rt.telegram.is_configured() {
        return;
    }
    let text = format!(
        "🟢 <b>دخول صفقة</b>\nزوج: <code>{pair}</code>\nنوع: <b>{side}</b>\nسعر الدخول: <code>{entry:.4}</code>\nالحجم: <code>{qty}</code>\nستоп: <code>{stop:.4}</code>\nهدف: <code>{target:.4}</code>"
    );
    let _ = rt.telegram.send_text(&text).await;
}

pub async fn trade_exit(
    rt: &SharedRuntime,
    pos: &MirrorPosition,
    order: &OrderResponse,
    fraction: f64,
) {
    if !rt.telegram.is_configured() {
        return;
    }
    let pct = if pos.entry > 0.0 {
        ((pos.current - pos.entry) / pos.entry) * 100.0
    } else {
        0.0
    };
    let pnl_usd = pos.pnl * fraction;
    let text = format!(
        "🔴 <b>إغلاق صفقة</b>\n{} ({:.0}%)\nزوج: <code>{}</code>\nPnL: <code>{:+.2} $</code> ({:+.2}%)\norder: <code>{}</code>",
        if fraction >= 0.99 { "إغلاق كامل" } else { "إغلاق جزئي" },
        fraction * 100.0,
        pos.pair,
        pnl_usd,
        pct,
        order.orderId
    );
    let _ = rt.telegram.send_text(&text).await;
}

pub async fn paper_trade_exit(rt: &SharedRuntime, symbol: &str, pnl_usd: f64, fraction: f64) {
    if !rt.telegram.is_configured() {
        return;
    }
    let text = format!(
        "🔴 <b>إغلاق Paper</b> ({:.0}%)\nرمز: <code>{symbol}</code>\nPnL: <code>{pnl_usd:+.2} $</code>\n📡 أسعار: سوق Binance الحي",
        fraction * 100.0
    );
    let _ = rt.telegram.send_text(&text).await;
}

pub async fn periodic_report(rt: &SharedRuntime) {
    if !rt.telegram.is_configured() {
        return;
    }
    let m = rt.refresh_mirror().await;
    let text = format!(
        "📊 <b>تقرير صقر</b>\nالرصيد: <code>{:.2} $</code>\nاليوم: <code>{:+.2}%</code>\nصفقات مفتوحة: <code>{}</code>\nرابحة: <code>{:+.2} $</code> | خاسرة: <code>-{:.2} $</code>",
        m.total_balance_usd,
        m.daily_profit_pct,
        m.open_positions_count,
        m.winning_pnl_usd,
        m.losing_pnl_usd
    );
    let _ = rt.telegram.send_text(&text).await;
}
