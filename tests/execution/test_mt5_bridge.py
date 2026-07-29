from execution.mt5_bridge import MT5Bridge, is_windows, map_symbol


def test_map_symbol_xm():
    assert map_symbol("BTC/USDT") == "BTCUSD"
    assert map_symbol("ETH/USDT") == "ETHUSD"


def test_mt5_connect_disabled(monkeypatch):
    class S:
        mt5_enabled = False
        mt5_login = "1"
        mt5_password = "x"
        mt5_server = "XMGlobal-MT5 10"

    monkeypatch.setattr("execution.mt5_bridge.get_settings", lambda: S())
    bridge = MT5Bridge()
    try:
        bridge.connect()
        assert False, "should raise"
    except Exception as exc:
        assert "MT5_ENABLED" in str(exc)


def test_mt5_requires_windows_when_enabled(monkeypatch):
    class S:
        mt5_enabled = True
        mt5_login = "345814054"
        mt5_password = "secret"
        mt5_server = "XMGlobal-MT5 10"

    monkeypatch.setattr("execution.mt5_bridge.get_settings", lambda: S())
    monkeypatch.setattr("execution.mt5_bridge.is_windows", lambda: False)
    bridge = MT5Bridge()
    try:
        bridge.connect()
        assert False, "should raise"
    except Exception as exc:
        assert "Windows" in str(exc)
