"""
SoccerSolver - Test Suite: FastAPI Server and Web Endpoints
"""

from fastapi.testclient import TestClient
from soccersolver.server import app

client = TestClient(app)


def test_index_html_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "SoccerSolver" in response.text
    assert "Decision Solver" in response.text


def test_api_data_stats():
    response = client.get("/api/data/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["record_counts"]["players"] > 0
    assert data["record_counts"]["player_valuations"] > 0


def test_api_solve_endpoint():
    response = client.post("/api/solve", json={
        "query": "we need a left back under 3M€ who fits LaLiga",
        "auto_stage_hitl": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPTIMAL"
    assert len(data["solution"]["candidates"]) > 0


def test_api_backtest_endpoint():
    response = client.post("/api/backtest", json={
        "historical_season": "2022/2023",
        "position": "Left-Back",
        "budget": 3000000.0,
        "top_k": 3
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["top_recommendations"]) == 3


def test_api_hitl_and_observability():
    resp_actions = client.get("/api/hitl/actions")
    assert resp_actions.status_code == 200

    resp_metrics = client.get("/api/observability/metrics")
    assert resp_metrics.status_code == 200

    resp_traces = client.get("/api/observability/traces")
    assert resp_traces.status_code == 200


def test_api_search_players_paginated():
    response = client.get("/api/data/players?page=1&page_size=5&search=Pedri")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["players"]) <= 5
    assert any("pedri" in p["name"].lower() for p in data["players"])
