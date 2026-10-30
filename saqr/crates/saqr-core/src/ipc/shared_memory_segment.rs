/// POSIX Shared Memory — Zero-Copy IPC (placeholder segment id)
pub struct PosixSharedMemorySegment {
    pub segment_name: String,
    pub byte_size: usize,
}

impl PosixSharedMemorySegment {
    pub fn new(segment_name: String, byte_size: usize) -> Self {
        Self {
            segment_name,
            byte_size,
        }
    }

    pub fn layout_valid(&self) -> bool {
        self.byte_size >= std::mem::size_of::<crate::core::unified_market_state::UnifiedMarketState>()
    }
}
