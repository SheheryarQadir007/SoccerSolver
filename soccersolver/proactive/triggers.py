"""
SoccerSolver - Event-Driven Proactivity
Listens to football events (injuries, contract expiry windows, market valuation anomalies)
and proactively triggers mathematical problem solving without waiting for user queries.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from soccersolver.data.repository import FootballDataRepository
from soccersolver.optimization.formalizer import ProblemFormalizer
from soccersolver.optimization.solver import MathematicalOptimizationSolver
from soccersolver.hitl.queue import ActionQueue
from soccersolver.hitl.models import ActionType


class ProactiveEventEngine:
    def __init__(
        self,
        repo: Optional[FootballDataRepository] = None,
        formalizer: Optional[ProblemFormalizer] = None,
        solver: Optional[MathematicalOptimizationSolver] = None,
        queue: Optional[ActionQueue] = None
    ):
        self.repo = repo or FootballDataRepository()
        self.formalizer = formalizer or ProblemFormalizer()
        self.solver = solver or MathematicalOptimizationSolver(self.repo)
        self.queue = queue or ActionQueue()

    def handle_injury_event(
        self,
        club_name: str,
        injured_player_name: str,
        position: str,
        budget_eur: float = 3_000_000.0,
        expected_layoff_months: int = 6
    ) -> Dict[str, Any]:
        """
        Proactively triggers emergency recruitment solution when a squad member suffers injury.
        """
        query = (
            f"Emergency replacement for {injured_player_name} ({position}) at {club_name}. "
            f"Need a {position} under {int(budget_eur/1e6)}M€ who fits LaLiga immediately with high tactical fit."
        )

        spec, metrics = self.formalizer.formalize(query)
        solution = self.solver.solve(spec)

        staged_actions = []
        if solution.candidates:
            top_candidate = solution.candidates[0]

            # Stage a proposed scouting dispatch and agent inquiry into HITL queue
            action_scout = self.queue.stage_action(
                action_type=ActionType.DISPATCH_SCOUT,
                player_id=top_candidate.player_id,
                player_name=top_candidate.name,
                target_club=top_candidate.current_club_name,
                summary=f"Emergency scouting mission for {top_candidate.name} to cover {injured_player_name}'s {expected_layoff_months}-month layoff at {club_name}.",
                payload={
                    "event": "INJURY_REPLACEMENT",
                    "injured_player": injured_player_name,
                    "target_club": club_name,
                    "candidate_score": top_candidate.composite_score,
                    "tactical_fit": top_candidate.tactical_fit_score,
                    "market_value_eur": top_candidate.market_value_eur,
                    "citation_url": top_candidate.data_citation_url
                },
                estimated_cost=2500.0,
                impact_level="HIGH"
            )
            staged_actions.append(action_scout)

        return {
            "event_type": "SQUAD_INJURY_EMERGENCY",
            "injured_player": injured_player_name,
            "club": club_name,
            "position": position,
            "solution_status": solution.status,
            "top_candidate": solution.candidates[0].name if solution.candidates else None,
            "staged_actions_count": len(staged_actions),
            "staged_actions": [a.action_id for a in staged_actions]
        }

    def scan_contract_expiry_opportunities(
        self,
        position: Optional[str] = None,
        max_budget: float = 10_000_000.0,
        target_league: str = "ES1",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Proactively scans the real database for high-value targets entering contract expiration windows across any position.
        """
        candidates = self.repo.query_candidates(
            sub_position=position,
            max_market_value=max_budget,
            min_minutes=400,
            target_league_code=target_league,
            limit=40
        )

        expiring_deals = []
        for c in candidates:
            exp_date = c.get("contract_expiration_date") or ""
            # Filter players whose contract expires in 2025 or 2026
            if "2025" in exp_date or "2026" in exp_date:
                action = self.queue.stage_action(
                    action_type=ActionType.CONTACT_AGENCY,
                    player_id=c["player_id"],
                    player_name=c["name"],
                    target_club=c.get("current_club_name", "Free Agent"),
                    summary=f"Contract expiration leverage: {c['name']} has expiring contract ({exp_date[:10]}). Contact agency for preliminary wage terms.",
                    payload={
                        "event": "CONTRACT_EXPIRATION_LEVERAGE",
                        "contract_expiry": exp_date,
                        "market_value_eur": c["market_value_in_eur"],
                        "profile_url": c["profile_url"]
                    },
                    estimated_cost=0.0,
                    impact_level="MEDIUM"
                )
                expiring_deals.append({
                    "player_id": c["player_id"],
                    "name": c["name"],
                    "club": c.get("current_club_name"),
                    "contract_expiration": exp_date,
                    "market_value": c["market_value_in_eur"],
                    "staged_action_id": action.action_id
                })
                if len(expiring_deals) >= limit:
                    break

        return expiring_deals
