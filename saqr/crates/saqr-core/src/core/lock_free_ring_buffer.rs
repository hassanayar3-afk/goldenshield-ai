use std::sync::atomic::{AtomicU64, Ordering};

use super::market_event::MarketEvent;

pub const RING_BUFFER_SIZE: usize = 1024;

pub struct LockFreeRingBuffer {
    buffer: [MarketEvent; RING_BUFFER_SIZE],
    head: AtomicU64,
    tail: AtomicU64,
}

impl LockFreeRingBuffer {
    pub const fn new() -> Self {
        const EMPTY_EVENT: MarketEvent = MarketEvent {
            symbol_hash: 0,
            price_scaled: 0,
            volume_scaled: 0,
            is_buyer_maker: false,
            timestamp_ns: 0,
        };
        Self {
            buffer: [EMPTY_EVENT; RING_BUFFER_SIZE],
            head: AtomicU64::new(0),
            tail: AtomicU64::new(0),
        }
    }

    #[inline(always)]
    pub fn try_push(&mut self, event: MarketEvent) -> Result<(), &'static str> {
        let current_tail = self.tail.load(Ordering::Relaxed);
        let current_head = self.head.load(Ordering::Acquire);

        if current_tail.wrapping_sub(current_head) >= RING_BUFFER_SIZE as u64 {
            return Err("RING_BUFFER_FULL: Event dropped to prevent blocking");
        }

        let index = (current_tail as usize) & (RING_BUFFER_SIZE - 1);
        self.buffer[index] = event;
        self.tail
            .store(current_tail.wrapping_add(1), Ordering::Release);
        Ok(())
    }

    #[inline(always)]
    pub fn try_pop(&mut self) -> Option<MarketEvent> {
        let current_head = self.head.load(Ordering::Relaxed);
        let current_tail = self.tail.load(Ordering::Acquire);
        if current_head == current_tail {
            return None;
        }
        let index = (current_head as usize) & (RING_BUFFER_SIZE - 1);
        let event = self.buffer[index];
        self.head
            .store(current_head.wrapping_add(1), Ordering::Release);
        Some(event)
    }
}

impl Default for LockFreeRingBuffer {
    fn default() -> Self {
        Self::new()
    }
}
