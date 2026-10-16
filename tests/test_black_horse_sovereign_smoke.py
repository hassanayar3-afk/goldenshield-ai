"""Smoke imports for Black Horse 2.0 sovereign layers."""

from __future__ import annotations


def test_neural_matrix_import():
    import core_engine.neural_matrix as nm

    assert hasattr(nm, "main")


def test_gateway_app():
    from gateway_api.fast_router import app

    assert app.title == "GoldenShield Gateway"


def test_live_token_helper():
    from terminal_app.routes.api_live import live_stream_auth_ok_token

    assert live_stream_auth_ok_token("") is False
