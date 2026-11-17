"""
SoccerSolver - Test Suite: Problem Formalizer and Math Constraints
"""

import pytest
from soccersolver.optimization.formalizer import ProblemFormalizer
from soccersolver.optimization.models import ConstraintType


def test_formalize_left_back_query():
    formalizer = ProblemFormalizer()
    query = "we need a left back under 3M€ who fits LaLiga"
    spec, metrics = formalizer.formalize(query)

    assert spec.target_position == "Left-Back"
    assert spec.max_budget_eur == 3_000_000.0
    assert spec.target_league_code == "ES1"
    assert len(spec.constraints) >= 3
    assert "\\begin{aligned}" in spec.mathematical_formulation_latex
    assert "3,000,000" in spec.mathematical_formulation_latex


def test_formalize_midfield_query_with_age():
    formalizer = ProblemFormalizer()
    query = "we need a central midfielder under 5M EUR, age under 23, with high progressive passing"
    spec, metrics = formalizer.formalize(query)

    assert spec.target_position == "Central Midfield"
    assert spec.max_budget_eur == 5_000_000.0
    assert spec.max_age == 23
    assert spec.weights.tactical_fit > 0.0


def test_budget_formats_parsing():
    formalizer = ProblemFormalizer()
    cases = [
        ("striker under 2.5m", 2_500_000.0),
        ("winger under 800k", 800_000.0),
        ("centre back max €4,000,000", 4_000_000.0),
    ]
    for text, expected in cases:
        b = formalizer._parse_budget(text)
        assert b == expected, f"Failed for {text}: got {b}, expected {expected}"
