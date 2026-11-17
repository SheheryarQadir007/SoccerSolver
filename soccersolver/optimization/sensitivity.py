"""
SoccerSolver - Sensitivity & Constraint Slack Analysis
Computes shadow prices, trade-off elasticity, and identifies binding constraints.
"""

from typing import List, Dict, Any, Tuple
from soccersolver.optimization.models import SensitivityAnalysis, OptimizationSpec


class SensitivityAnalyzer:
    @staticmethod
    def analyze(
        spec: OptimizationSpec,
        top_candidate: Dict[str, Any],
        all_eligible_candidates: List[Dict[str, Any]],
        relaxed_budget_candidates: List[Dict[str, Any]]
    ) -> SensitivityAnalysis:
        top_cost = top_candidate.get("market_value_in_eur", 0.0)
        budget = spec.max_budget_eur
        slack_budget = max(0.0, budget - top_cost)

        # Calculate shadow price: quality gain if budget is relaxed by 15%
        base_score = top_candidate.get("composite_score", 75.0)
        best_relaxed_score = base_score

        for c in relaxed_budget_candidates:
            score = c.get("composite_score", 0.0)
            if score > best_relaxed_score:
                best_relaxed_score = score

        score_gain_pct = round(((best_relaxed_score - base_score) / max(base_score, 1.0)) * 100.0, 2)
        score_gain_pct = max(0.0, score_gain_pct)

        # Budget elasticity per 100k EUR
        budget_delta_100k = (budget * 0.15) / 100_000.0
        elasticity = round(score_gain_pct / max(budget_delta_100k, 1.0), 3)

        # Identify binding constraints
        binding = []
        if slack_budget < budget * 0.10:
            binding.append(f"Budget Constraint (€{budget:,.0f}) is TIGHT: only €{slack_budget:,.0f} slack remaining.")
        else:
            binding.append(f"Budget Constraint has healthy slack: €{slack_budget:,.0f} unspent capital.")

        if spec.max_age:
            binding.append(f"Age Constraint (<= {spec.max_age} years) filtered older experienced profiles.")

        binding.append(f"Minutes threshold (>={spec.min_minutes_played} mins) enforced statistical reliability.")

        # Actionable trade-off notes
        if score_gain_pct > 5.0:
            tradeoff_notes = (
                f"High financial leverage: Relaxing the budget by 15% (+€{budget * 0.15:,.0f}) yields a "
                f"+{score_gain_pct:.1f}% gain in composite scout rating (elasticity {elasticity:.2f} pts/100k€). "
                f"Consider recommending a small budget extension to the Sporting Director."
            )
        else:
            tradeoff_notes = (
                f"Diminishing returns above €{budget:,.0f}: Top candidate '{top_candidate.get('name')}' captures "
                f"the near-optimal frontier. Additional capital yields marginal tactical gain (< {max(score_gain_pct, 1.0):.1f}%)."
            )

        return SensitivityAnalysis(
            budget_shadow_price_pct=score_gain_pct,
            budget_elasticity=elasticity,
            slack_budget_eur=round(slack_budget, 2),
            binding_constraints=binding,
            tradeoff_notes=tradeoff_notes
        )
