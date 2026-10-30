/// recvWindow الافتراضي لباينانس (ms)
pub const DEFAULT_RECV_WINDOW: u64 = 5000;

pub fn validate_timestamp_window(
    exchange_ts: u64,
    local_safe_ts: u64,
    recv_window: u64,
) -> bool {
    local_safe_ts.abs_diff(exchange_ts) <= recv_window
}
