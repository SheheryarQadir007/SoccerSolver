"""
SoccerSolver - Test Suite: Generalization across ANY position, ANY budget, ANY league, and PLAYER SIMILARITY
"""

import pytest
from soccersolver.agent.orchestrator import DecisionMakingAgent
from soccersolver.backtest.engine import BacktestEngine


def test_striker_under_20m_premier_league():
    agent = DecisionMakingAgent()
    res = agent.process_recruitment_query("striker under 20M for Premier League")

    spec = res["formalized_spec"]
    sol = res["solution"]

    assert spec["target_position"] == "Centre-Forward"
    assert spec["target_league_code"] == "GB1"
    assert spec["max_budget_eur"] == 20_000_000.0
    assert sol["status"] == "OPTIMAL"
    assert len(sol["candidates"]) > 0

    top = sol["candidates"][0]
    assert top["market_value_eur"] <= 20_000_000.0
    assert top["sub_position"] == "Centre-Forward"


def test_centre_back_under_10m_serie_a():
    agent = DecisionMakingAgent()
    res = agent.process_recruitment_query("centre back under 10M in Serie A")

    spec = res["formalized_spec"]
    sol = res["solution"]

    assert spec["target_position"] == "Centre-Back"
    assert spec["target_league_code"] == "IT1"
    assert spec["max_budget_eur"] == 10_000_000.0
    assert sol["status"] == "OPTIMAL"
    assert len(sol["candidates"]) > 0

    top = sol["candidates"][0]
    assert top["market_value_eur"] <= 10_000_000.0
    assert top["sub_position"] == "Centre-Back"


def test_player_replacement_similarity_pedri():
    agent = DecisionMakingAgent()
    res = agent.process_recruitment_query("replacement for Pedri under 15M")

    spec = res["formalized_spec"]
    sol = res["solution"]

    assert spec["reference_player_name"] == "Pedri"
    assert spec["max_budget_eur"] == 15_000_000.0
    assert sol["status"] == "OPTIMAL"
    assert len(sol["candidates"]) > 0

    top = sol["candidates"][0]
    assert top["similarity_to_reference"] is not None
    assert top["similarity_to_reference"] > 70.0
    assert "Pedri" in top["decision_rationale"]


def test_winger_under_30m_bundesliga():
    agent = DecisionMakingAgent()
    res = agent.process_recruitment_query("winger under 30M for Bundesliga")

    spec = res["formalized_spec"]
    sol = res["solution"]

    assert spec["target_league_code"] == "L1"
    assert spec["max_budget_eur"] == 30_000_000.0
    assert sol["status"] == "OPTIMAL"
    assert len(sol["candidates"]) > 0

    top = sol["candidates"][0]
    assert top["sub_position"] in ("Left Winger", "Right Winger")


def test_backtest_any_position():
    engine = BacktestEngine()
    for pos in ["Centre-Forward", "Centre-Back", "Central Midfield"]:
        rep = engine.run_backtest(
            historical_season="2022/2023",
            position=pos,
            budget=15_000_000.0,
            top_k=3
        )
        assert rep.total_candidates_screened > 0
        assert len(rep.top_recommendations) == 3
        assert rep.portfolio_hit_rate_pct >= 0.0
        assert rep.roi_multiple > 0.0
