"""
SoccerSolver - Test Suite: Proactivity, Observability, and End-to-End Agent
"""

import pytest
from soccersolver.proactive.triggers import ProactiveEventEngine
from soccersolver.observability.tracker import ObservabilityTracker
from soccersolver.agent.orchestrator import DecisionMakingAgent


def test_proactive_injury_trigger():
    engine = ProactiveEventEngine()
    res = engine.handle_injury_event(
        club_name="Getafe CF",
        injured_player_name="Diego Rico",
        position="Left-Back",
        budget_eur=3_000_000.0
    )
    assert res["event_type"] == "SQUAD_INJURY_EMERGENCY"
    assert res["top_candidate"] is not None
    assert res["staged_actions_count"] > 0


def test_proactive_expiry_scan():
    engine = ProactiveEventEngine()
    deals = engine.scan_contract_expiry_opportunities(max_budget=4_000_000.0, limit=2)
    assert len(deals) > 0
    for d in deals:
        assert d["name"] is not None
        assert "contract_expiration" in d


def test_observability_tracker_cost_calculation():
    tracker = ObservabilityTracker()
    cost = tracker.calculate_cost("gemini-2.0-flash", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0.0

    summary = tracker.get_summary_metrics()
    assert summary["total_runs"] >= 0


def test_end_to_end_agent_workflow():
    agent = DecisionMakingAgent()
    res = agent.process_recruitment_query("we need a left back under 3M€ who fits LaLiga")

    assert res["status"] == "OPTIMAL"
    assert len(res["solution"]["candidates"]) > 0
    assert res["staged_hitl_action"] is not None
    assert res["observability_trace"]["estimated_cost_usd"] >= 0.0
    assert res["execution_time_ms"] > 0.0
