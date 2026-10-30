use std::collections::HashMap;

use parking_lot::Mutex;
use serde::{Deserialize, Serialize};

use crate::binance::mirror::{BinanceMirrorPayload, MirrorPosition};
use crate::binance::market_public::BinancePublicMarket;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaperPosition {
    pub symbol: String,
    pub qty: f64,
    pub entry_price: f64,
    pub side: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaperTradeRecord {
    pub symbol: String,
    pub pair: String,
    pub side: String,
    pub qty: f64,
    pub entry: f64,
    pub exit: f64,
    pub pnl_usd: f64,
    pub closed_at_ms: u64,
}

pub struct PaperEngine {
    inner: Mutex<PaperState>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct PaperState {
    initial_usdt: f64,
    usdt_cash: f64,
    positions: HashMap<String, PaperPosition>,
    history: Vec<PaperTradeRecord>,
    session_start_ms: u64,
}

impl PaperEngine {
    pub fn new(initial_usdt: f64) -> Self {
        let now = now_ms();
        Self {
            inner: Mutex::new(PaperState {
                initial_usdt,
                usdt_cash: initial_usdt,
                positions: HashMap::new(),
                history: Vec::new(),
                session_start_ms: now,
            }),
        }
    }

    pub async fn build_mirror(
        &self,
        market: &BinancePublicMarket,
        symbol: &str,
        bot_running: bool,
    ) -> BinanceMirrorPayload {
        let st = self.inner.lock().clone();
        let btc_price = market.price(symbol).await.unwrap_or(0.0);

        let mut positions_out: Vec<MirrorPosition> = Vec::new();
        let mut notional = 0.0_f64;
        let mut winning = 0.0_f64;
        let mut losing = 0.0_f64;

        for (sym, pos) in &st.positions {
            let px = market.price(sym).await.unwrap_or(pos.entry_price);
            let pnl = (px - pos.entry_price) * pos.qty;
            notional += pos.qty * px;
            if pnl >= 0.0 {
                winning += pnl;
            } else {
                losing += pnl.abs();
            }
            let base = sym.strip_suffix("USDT").unwrap_or(sym);
            positions_out.push(MirrorPosition {
                id: sym.clone(),
                pair: format!("{base}/USDT"),
                symbol: sym.clone(),
                asset: base.to_string(),
                side: pos.side.clone(),
                lot: format!("{:.8}", pos.qty),
                entry: pos.entry_price,
                current: px,
                pnl,
            });
        }

        let total = st.usdt_cash + notional;
        let daily_pct = if st.initial_usdt > 0.0 {
            ((total - st.initial_usdt) / st.initial_usdt) * 100.0
        } else {
            0.0
        };

        BinanceMirrorPayload {
            ok: btc_price > 0.0,
            source: "paper_live_market",
            total_balance_usd: total.max(st.initial_usdt),
            daily_profit_pct: daily_pct,
            open_positions_count: positions_out.len(),
            winning_pnl_usd: winning,
            losing_pnl_usd: losing,
            usdt_free: st.usdt_cash,
            usdt_locked: notional,
            initial_balance_usd: st.initial_usdt,
            bot_running,
            positions: positions_out,
            error: if btc_price > 0.0 {
                None
            } else {
                Some("market_data_unavailable".into())
            },
        }
    }

    pub fn close_symbol(&self, symbol: &str, fraction: f64, exit_price: f64) -> Result<f64, String> {
        let mut st = self.inner.lock();
        let pos = st
            .positions
            .get(symbol)
            .cloned()
            .ok_or_else(|| "position_not_found".to_string())?;
        let frac = fraction.clamp(0.05, 1.0);
        let close_qty = pos.qty * frac;
        if close_qty <= 0.0 {
            return Err("qty_too_small".into());
        }
        let proceeds = close_qty * exit_price;
        let pnl = (exit_price - pos.entry_price) * close_qty;
        st.usdt_cash += proceeds;
        let base = symbol.strip_suffix("USDT").unwrap_or(symbol);
        st.history.push(PaperTradeRecord {
            symbol: symbol.to_string(),
            pair: format!("{base}/USDT"),
            side: "SELL".into(),
            qty: close_qty,
            entry: pos.entry_price,
            exit: exit_price,
            pnl_usd: pnl,
            closed_at_ms: now_ms(),
        });
        if frac >= 0.99 {
            st.positions.remove(symbol);
        } else {
            let mut p = pos;
            p.qty -= close_qty;
            st.positions.insert(symbol.to_string(), p);
        }
        Ok(pnl)
    }

    pub fn close_filtered<F>(&self, prices: &HashMap<String, f64>, pred: F) -> u32
    where
        F: Fn(&f64) -> bool,
    {
        let symbols: Vec<String> = self
            .inner
            .lock()
            .positions
            .keys()
            .cloned()
            .collect();
        let mut closed = 0;
        for sym in symbols {
            let px = prices.get(&sym).copied().unwrap_or(0.0);
            if px <= 0.0 {
                continue;
            }
            let pnl = {
                let st = self.inner.lock();
                st.positions
                    .get(&sym)
                    .map(|p| (px - p.entry_price) * p.qty)
                    .unwrap_or(0.0)
            };
            if pred(&pnl) {
                if self.close_symbol(&sym, 1.0, px).is_ok() {
                    closed += 1;
                }
            }
        }
        closed
    }

    pub fn market_buy(&self, symbol: &str, usdt_spend: f64, price: f64) -> Result<f64, String> {
        if price <= 0.0 || usdt_spend <= 0.0 {
            return Err("invalid_price_or_size".into());
        }
        let mut st = self.inner.lock();
        if st.usdt_cash < usdt_spend {
            return Err("insufficient_paper_usdt".into());
        }
        let qty = usdt_spend / price;
        st.usdt_cash -= usdt_spend;
        let entry = st.positions.entry(symbol.to_string()).or_insert(PaperPosition {
            symbol: symbol.to_string(),
            qty: 0.0,
            entry_price: price,
            side: "BUY".into(),
        });
        let total_qty = entry.qty + qty;
        entry.entry_price = ((entry.entry_price * entry.qty) + (price * qty)) / total_qty;
        entry.qty = total_qty;
        Ok(qty)
    }

    pub fn history(&self) -> Vec<PaperTradeRecord> {
        self.inner.lock().history.clone()
    }

    pub fn report(&self, period: &str) -> serde_json::Value {
        let st = self.inner.lock();
        let now = now_ms();
        let window_ms = match period {
            "weekly" => 7 * 86_400_000,
            "monthly" => 30 * 86_400_000,
            _ => 86_400_000,
        };
        let mut win_amt = 0.0;
        let mut loss_amt = 0.0;
        let mut win_n = 0_u32;
        let mut loss_n = 0_u32;
        let cutoff = now.saturating_sub(window_ms);
        for t in &st.history {
            if t.closed_at_ms < cutoff {
                continue;
            }
            if t.pnl_usd >= 0.0 {
                win_amt += t.pnl_usd;
                win_n += 1;
            } else {
                loss_amt += t.pnl_usd.abs();
                loss_n += 1;
            }
        }
        serde_json::json!({
            "period": period,
            "win_amount_usd": win_amt,
            "loss_amount_usd": loss_amt,
            "win_count": win_n,
            "loss_count": loss_n,
            "initial_balance_usd": st.initial_usdt,
        })
    }
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}
