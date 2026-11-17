"""
SoccerSolver - Test Suite: Real Football Data & Citations Integrity
Validates that all player records are verified with public source citations and profile URLs.
"""

import sqlite3
import pytest
from soccersolver.config import DB_PATH
from soccersolver.data.repository import FootballDataRepository


def test_database_exists_and_populated():
    assert DB_PATH.exists(), f"Database missing at {DB_PATH}"
    with sqlite3.connect(str(DB_PATH)) as conn:
        cur = conn.cursor()
        
        # Verify core tables
        for table in ["competitions", "clubs", "players", "player_valuations", "player_seasons", "transfers", "tactical_profiles"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            assert count > 0, f"Table {table} must not be empty"

 
def test_data_citations_present():
    repo = FootballDataRepository()
    candidates = repo.query_candidates(sub_position="Left-Back", max_market_value=3000000, limit=10)
    assert len(candidates) > 0

    for cand in candidates:
        assert cand.get("data_citation"), f"Player {cand['name']} must have a citation"
        assert "Transfermarkt" in cand["data_citation"]
        assert cand.get("profile_url"), f"Player {cand['name']} must have a profile URL"
        assert "transfermarkt" in cand["profile_url"].lower()


def test_disagreement_notes_generated():
    repo = FootballDataRepository()
    candidates = repo.query_candidates(sub_position="Left-Back", max_market_value=3000000, limit=20)
    # At least some candidates should have peak > current valuation triggering discrepancy notes
    notes = [c.get("data_disagreement_notes") for c in candidates if c.get("data_disagreement_notes")]
    assert len(notes) > 0
