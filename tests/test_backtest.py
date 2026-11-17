"""
SoccerSolver - Test Suite: Historical Backtesting Engine
"""

import pytest
from soccersolver.backtest.engine import BacktestEngine


def test_historical_backtest_2022():
    engine = BacktestEngine()
    rep = engine.run_backtest(
        historical_season="2022/2023",
        position="Left-Back",
        budget=3_000_000.0,
        top_k=5
    )

    assert rep.historical_season == "2022/2023"
    assert rep.total_candidates_screened > 0
    assert len(rep.top_recommendations) == 5
    assert rep.portfolio_hit_rate_pct >= 0.0
    assert rep.roi_multiple > 0.0

    # Ensure all recommendations were evaluated forward
    for r in rep.top_recommendations:
        assert r.forward_market_value_eur >= 0.0
        assert r.verdict is not None
        assert "transfermarkt" in r.historical_profile_url.lower()
