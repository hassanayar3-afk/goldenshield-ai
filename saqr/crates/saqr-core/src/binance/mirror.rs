use serde::Serialize;

use super::exchange_rules::{floor_to_step, format_qty_string};
use super::signed_api::BinanceSignedClient;
use crate::config::env_settings::SaqrSettings;

#[derive(Debug, Clone, Serialize)]
pub struct MirrorPosition {
    pub id: String,
    pub pair: String,
    pub symbol: String,
    pub asset: String,
    #[serde(rename = "type")]
    pub side: String,
    pub lot: String,
    pub entry: f64,
    pub current: f64,
    pub pnl: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct BinanceMirrorPayload {
    pub ok: bool,
    pub source: &'static str,
    pub total_balance_usd: f64,
    pub daily_profit_pct: f64,
    pub open_positions_count: usize,
    pub winning_pnl_usd: f64,
    pub losing_pnl_usd: f64,
    pub usdt_free: f64,
    pub usdt_locked: f64,
    pub initial_balance_usd: f64,
    pub bot_running: bool,
    pub positions: Vec<MirrorPosition>,
    pub error: Option<String>,
}

pub async fn build_mirror(
    client: &BinanceSignedClient,
    settings: &SaqrSettings,
    bot_running: bool,
    fallback: Option<&BinanceMirrorPayload>,
) -> BinanceMirrorPayload {
    let floor_balance = settings.initial_balance_usd.max(1.0);
    if !client.configured() {
        return degraded(floor_balance, bot_running, "missing_api_keys", fallback);
    }

    if let Err(e) = client.sync_time().await {
        tracing::warn!("binance time sync: {e}");
    }
    let _ = client.refresh_exchange_rules().await;

    let account = match client.account().await {
        Ok(a) => a,
        Err(e) => {
            tracing::warn!("binance account: {e}");
            return degraded(floor_balance, bot_running, &e, fallback);
        }
    };

    let prices = match client.ticker_prices_map().await {
        Ok(p) => p,
        Err(e) => {
            tracing::warn!("binance prices: {e}");
            return degraded(floor_balance, bot_running, &e, fallback);
        }
    };

    let mut usdt_free = 0.0_f64;
    let mut usdt_locked = 0.0_f64;
    let mut positions: Vec<MirrorPosition> = Vec::new();
    let mut positions_notional = 0.0_f64;

    for bal in &account.balances {
        let free: f64 = bal.free.parse().unwrap_or(0.0);
        let locked: f64 = bal.locked.parse().unwrap_or(0.0);
        let total = free + locked;
        if bal.asset == "USDT" {
            usdt_free = free;
            usdt_locked = locked;
            continue;
        }
        if total <= 0.0 {
            continue;
        }
        let symbol = format!("{}USDT", bal.asset);
        let price = match prices.get(&symbol) {
            Some(p) => *p,
            None => continue,
        };
        let entry = estimate_entry_price(client, &symbol, total).await;
        let notional = total * price;
        positions_notional += notional;
        let pnl = if entry > 0.0 {
            (price - entry) * total
        } else {
            0.0
        };
        positions.push(MirrorPosition {
            id: symbol.clone(),
            pair: format!("{}/USDT", bal.asset),
            symbol: symbol.clone(),
            asset: bal.asset.clone(),
            side: "BUY".into(),
            lot: format_qty_for_symbol(client, &symbol, total),
            entry,
            current: price,
            pnl,
        });
    }

    let total_balance_usd = usdt_free + usdt_locked + positions_notional;
    let total_balance_usd = if total_balance_usd > 0.0 {
        total_balance_usd
    } else {
        fallback
            .map(|f| f.total_balance_usd)
            .unwrap_or(floor_balance)
    };

    let (winning, losing) = positions.iter().fold((0.0, 0.0), |(w, l), p| {
        if p.pnl >= 0.0 {
            (w + p.pnl, l)
        } else {
            (w, l + p.pnl.abs())
        }
    });

    let daily_profit_pct = daily_pnl_pct(client, settings, total_balance_usd).await;

    BinanceMirrorPayload {
        ok: true,
        source: "binance_testnet",
        total_balance_usd,
        daily_profit_pct,
        open_positions_count: positions.len(),
        winning_pnl_usd: winning,
        losing_pnl_usd: losing,
        usdt_free,
        usdt_locked,
        initial_balance_usd: settings.initial_balance_usd,
        bot_running,
        positions,
        error: None,
    }
}

fn format_qty_for_symbol(client: &BinanceSignedClient, symbol: &str, qty: f64) -> String {
    if let Some(rules) = client.rules_cache.get(symbol) {
        format_qty_string(qty, rules.step_size)
    } else {
        format!("{qty:.6}")
    }
}

async fn estimate_entry_price(client: &BinanceSignedClient, symbol: &str, qty: f64) -> f64 {
    let trades = client.my_trades(symbol, None).await.unwrap_or_default();
    if trades.is_empty() {
        return 0.0;
    }
    let mut cost = 0.0_f64;
    let mut held = 0.0_f64;
    for t in trades {
        let q: f64 = t.qty.parse().unwrap_or(0.0);
        let p: f64 = t.price.parse().unwrap_or(0.0);
        if t.isBuyer {
            cost += q * p;
            held += q;
        } else {
            let avg = if held > 0.0 { cost / held } else { p };
            let sell_q = q.min(held);
            cost -= sell_q * avg;
            held -= sell_q;
        }
    }
    if held > 0.0 && qty > 0.0 {
        cost / held
    } else {
        0.0
    }
}

async fn daily_pnl_pct(
    client: &BinanceSignedClient,
    settings: &SaqrSettings,
    total_balance_usd: f64,
) -> f64 {
    let start = utc_day_start_ms();
    let trades = client
        .my_trades(&settings.symbol, Some(start))
        .await
        .unwrap_or_default();
    let mut pnl = 0.0_f64;
    for t in &trades {
        let quote: f64 = t.quoteQty.parse().unwrap_or(0.0);
        if t.isBuyer {
            pnl -= quote;
        } else {
            pnl += quote;
        }
    }
    let base = settings.initial_balance_usd.max(total_balance_usd * 0.01);
    if base <= 0.0 {
        0.0
    } else {
        (pnl / base) * 100.0
    }
}

fn utc_day_start_ms() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let day = now / 86_400 * 86_400;
    day * 1000
}

fn degraded(
    floor_balance: f64,
    bot_running: bool,
    err: &str,
    fallback: Option<&BinanceMirrorPayload>,
) -> BinanceMirrorPayload {
    if let Some(f) = fallback {
        return BinanceMirrorPayload {
            ok: false,
            source: "cache",
            total_balance_usd: f.total_balance_usd.max(floor_balance),
            daily_profit_pct: f.daily_profit_pct,
            open_positions_count: f.open_positions_count,
            winning_pnl_usd: f.winning_pnl_usd,
            losing_pnl_usd: f.losing_pnl_usd,
            usdt_free: f.usdt_free,
            usdt_locked: f.usdt_locked,
            initial_balance_usd: f.initial_balance_usd,
            bot_running,
            positions: f.positions.clone(),
            error: Some(err.to_string()),
        };
    }
    BinanceMirrorPayload {
        ok: false,
        source: "fallback",
        total_balance_usd: floor_balance,
        daily_profit_pct: 0.0,
        open_positions_count: 0,
        winning_pnl_usd: 0.0,
        losing_pnl_usd: 0.0,
        usdt_free: floor_balance,
        usdt_locked: 0.0,
        initial_balance_usd: floor_balance,
        bot_running,
        positions: vec![],
        error: Some(err.to_string()),
    }
}

pub fn sell_qty_for_position(
    client: &BinanceSignedClient,
    symbol: &str,
    qty: f64,
    fraction: f64,
) -> Option<String> {
    let rules = client.rules_cache.get(symbol)?;
    let q = floor_to_step(qty * fraction, rules.step_size);
    if q <= 0.0 {
        return None;
    }
    Some(format_qty_string(q, rules.step_size))
}
