use std::collections::HashMap;
use std::sync::RwLock;

use serde::Deserialize;

#[derive(Debug, Clone)]
pub struct SymbolRules {
    pub step_size: f64,
    pub min_qty: f64,
    pub min_notional: f64,
}

#[derive(Debug, Deserialize)]
pub struct ExchangeInfoResponse {
    pub symbols: Vec<SymbolInfo>,
}

#[derive(Debug, Deserialize)]
struct SymbolInfo {
    symbol: String,
    filters: Vec<serde_json::Value>,
}

pub struct ExchangeRulesCache {
    rules: RwLock<HashMap<String, SymbolRules>>,
}

impl ExchangeRulesCache {
    pub fn new() -> Self {
        Self {
            rules: RwLock::new(HashMap::new()),
        }
    }

    pub fn upsert_from_exchange_info(&self, raw: &ExchangeInfoResponse) {
        let mut map = self.rules.write().expect("exchange rules lock");
        map.clear();
        for sym in &raw.symbols {
            if let Some(r) = parse_symbol(sym) {
                map.insert(sym.symbol.clone(), r);
            }
        }
    }

    pub fn get(&self, symbol: &str) -> Option<SymbolRules> {
        self.rules.read().ok()?.get(symbol).cloned()
    }
}

fn parse_symbol(sym: &SymbolInfo) -> Option<SymbolRules> {
    let mut step_size = 0.00000001_f64;
    let mut min_qty = 0.0_f64;
    let mut min_notional = 0.0_f64;
    for f in &sym.filters {
        let filter_type = f.get("filterType")?.as_str()?;
        match filter_type {
            "LOT_SIZE" => {
                step_size = f.get("stepSize")?.as_str()?.parse().ok()?;
                min_qty = f.get("minQty")?.as_str()?.parse().ok()?;
            }
            "NOTIONAL" | "MIN_NOTIONAL" => {
                if let Some(v) = f.get("minNotional").and_then(|x| x.as_str()) {
                    min_notional = v.parse().ok()?;
                }
            }
            _ => {}
        }
    }
    Some(SymbolRules {
        step_size,
        min_qty,
        min_notional,
    })
}

pub fn floor_to_step(qty: f64, step: f64) -> f64 {
    if step <= 0.0 || qty <= 0.0 {
        return 0.0;
    }
    let steps = (qty / step).floor();
    let v = steps * step;
    if v < 0.0 { 0.0 } else { v }
}

pub fn format_qty_string(qty: f64, step: f64) -> String {
    let q = floor_to_step(qty, step);
    if q <= 0.0 {
        return "0".into();
    }
    let decimals = step_decimals(step);
    format!("{:.prec$}", q, prec = decimals)
}

fn step_decimals(step: f64) -> usize {
    if step >= 1.0 {
        return 0;
    }
    let s = format!("{step}");
    if let Some(i) = s.find('.') {
        s[i + 1..].trim_end_matches('0').len()
    } else {
        0
    }
}

pub fn notional_ok(qty: f64, price: f64, rules: &SymbolRules) -> bool {
    qty >= rules.min_qty && qty * price >= rules.min_notional
}

