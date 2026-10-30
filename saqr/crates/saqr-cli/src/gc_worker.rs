use tokio::sync::mpsc;

/// Dedicated Async GC Thread — SPSC via mpsc
pub async fn run_gc_worker(mut rx: mpsc::Receiver<u64>) {
    while let Some(_token) = rx.recv().await {
        // تنظيف الكتائب المرفوضة — خارج hot path
    }
}
