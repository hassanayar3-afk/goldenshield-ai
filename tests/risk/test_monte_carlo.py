from risk.monte_carlo import run_monte_carlo


def test_monte_carlo_passes_with_high_win_probability():
    result = run_monte_carlo(win_probability=0.9, seed=42)
    assert result.passed is True
    assert result.win_rate >= 0.35


def test_monte_carlo_fails_with_low_win_probability():
    result = run_monte_carlo(win_probability=0.1, seed=42)
    assert result.passed is False


def test_monte_carlo_runs_1000_simulations():
    result = run_monte_carlo(win_probability=0.5, seed=1)
    assert result.simulations == 1000
