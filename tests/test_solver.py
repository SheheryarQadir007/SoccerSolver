"""
SoccerSolver - Test Suite: Mathematical Optimization Solver & Pareto Frontier
"""

import pytest
from soccersolver.optimization.formalizer import ProblemFormalizer
from soccersolver.optimization.solver import MathematicalOptimizationSolver


def test_solver_satisfies_all_hard_constraints():
    formalizer = ProblemFormalizer()
    solver = MathematicalOptimizationSolver()

    query = "we need a left back under 3M€ who fits LaLiga"
    spec, _ = formalizer.formalize(query)
    sol = solver.solve(spec)

    assert sol.status == "OPTIMAL"
    assert len(sol.candidates) > 0

    for c in sol.candidates:
        assert c.market_value_eur <= spec.max_budget_eur, f"{c.name} exceeded budget"
        assert c.sub_position == spec.target_position
        if spec.max_age:
            assert c.age <= spec.max_age, f"{c.name} exceeded max age"
        assert c.confidence_level > 0.0
        assert c.composite_score > 0.0


def test_pareto_frontier_and_slack():
    formalizer = ProblemFormalizer()
    solver = MathematicalOptimizationSolver()

    spec, _ = formalizer.formalize("we need a left back under 3M€ who fits LaLiga")
    sol = solver.solve(spec)

    assert sol.sensitivity.slack_budget_eur >= 0.0
    assert sol.sensitivity.budget_shadow_price_pct >= 0.0
    assert len(sol.sensitivity.binding_constraints) > 0
