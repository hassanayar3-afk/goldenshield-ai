from execution.mutex_guard import MutexGuard


def test_mutex_blocks_duplicate_symbol():
    guard = MutexGuard()
    assert guard.try_acquire("BTC/USDT") is True
    assert guard.try_acquire("BTC/USDT") is False


def test_mutex_allows_different_symbols():
    guard = MutexGuard()
    assert guard.try_acquire("BTC/USDT") is True
    assert guard.try_acquire("ETH/USDT") is True


def test_mutex_release_allows_reacquire():
    guard = MutexGuard()
    assert guard.try_acquire("BTC/USDT") is True
    guard.release("BTC/USDT")
    assert guard.try_acquire("BTC/USDT") is True


def test_mutex_is_locked_reflects_state():
    guard = MutexGuard()
    assert guard.is_locked("BTC/USDT") is False
    guard.try_acquire("BTC/USDT")
    assert guard.is_locked("BTC/USDT") is True
    guard.release("BTC/USDT")
    assert guard.is_locked("BTC/USDT") is False
