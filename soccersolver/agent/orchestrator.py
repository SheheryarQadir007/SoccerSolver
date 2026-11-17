"""
SoccerSolver - Decision-Making Agent Orchestrator
Explicit state machine coordinating tools, formal mathematical optimization,
HITL staging, and full observability tracking.
"""

import time
import uuid
from typing import Dict, Any, Optional, List

from soccersolver.data.repository import FootballDataRepository
from soccersolver.optimization.formalizer import ProblemFormalizer
from soccersolver.optimization.solver import MathematicalOptimizationSolver
from soccersolver.optimization.models import OptimizationSpec, OptimizationSolution
from soccersolver.backtest.engine import BacktestEngine
from soccersolver.hitl.queue import ActionQueue
from soccersolver.hitl.models import ActionType, ProposedAction
from soccersolver.observability.tracker import ObservabilityTracker, ToolExecutionRecord


class DecisionMakingAgent:
    def __init__(
        self,
        repo: Optional[FootballDataRepository] = None,
        formalizer: Optional[ProblemFormalizer] = None,
        solver: Optional[MathematicalOptimizationSolver] = None,
        backtester: Optional[BacktestEngine] = None,
        queue: Optional[ActionQueue] = None,
        tracker: Optional[ObservabilityTracker] = None,
        model_name: str = "gemini-2.0-flash"
    ):
        self.repo = repo or FootballDataRepository()
        self.formalizer = formalizer or ProblemFormalizer(model_name=model_name)
        self.solver = solver or MathematicalOptimizationSolver(self.repo)
        self.backtester = backtester or BacktestEngine(self.repo)
        self.queue = queue or ActionQueue()
        self.tracker = tracker or ObservabilityTracker()
        self.model_name = model_name

    def process_recruitment_query(
        self,
        user_query: str,
        trigger_type: str = "USER_QUERY",
        auto_stage_hitl: bool = True
    ) -> Dict[str, Any]:
        """
        Executes end-to-end decision-making workflow:
        Query -> Math Formalization -> Solver & Sensitivity -> HITL Staging -> Observability Log.
        """
        start_time = time.time()
        tool_records: List[ToolExecutionRecord] = []
        total_prompt_tokens = 0
        total_comp_tokens = 0
        run_id = f"RUN-{str(uuid.uuid4())[:8].upper()}"

        # Step 1: Formalize problem
        f_start = time.time()
        spec, f_metrics = self.formalizer.formalize(user_query)
        f_duration = (time.time() - f_start) * 1000.0
        total_prompt_tokens += f_metrics["prompt_tokens"]
        total_comp_tokens += f_metrics["completion_tokens"]

        tool_records.append(
            ToolExecutionRecord(
                tool_name="formalize_scouting_problem",
                arguments={"query": user_query},
                duration_ms=round(f_duration, 2),
                status="SUCCESS",
                output_summary=f"Formalized {len(spec.constraints)} constraints, target position: {spec.target_position}, budget: €{spec.max_budget_eur:,.0f}"
            )
        )

        # Step 2: Solve Mathematical Program
        s_start = time.time()
        solution = self.solver.solve(spec)
        s_duration = (time.time() - s_start) * 1000.0

        tool_records.append(
            ToolExecutionRecord(
                tool_name="solve_mathematical_optimization",
                arguments={"problem_id": spec.problem_id, "algorithm": solution.solver_algorithm},
                duration_ms=round(s_duration, 2),
                status=solution.status,
                output_summary=f"Evaluated candidates; found {len(solution.candidates)} Pareto/TOPSIS solutions. Top candidate: {solution.candidates[0].name if solution.candidates else 'None'}"
            )
        )

        # Step 3: Stage Proposed Action in Human-in-the-Loop Queue
        staged_action: Optional[ProposedAction] = None
        if auto_stage_hitl and solution.candidates:
            h_start = time.time()
            top_c = solution.candidates[0]
            staged_action = self.queue.stage_action(
                action_type=ActionType.DISPATCH_SCOUT,
                player_id=top_c.player_id,
                player_name=top_c.name,
                target_club=top_c.current_club_name,
                summary=f"Dispatch chief scout to observe optimal candidate {top_c.name} ({top_c.sub_position}, €{top_c.market_value_eur:,.0f}) in upcoming league fixture.",
                payload={
                    "run_id": run_id,
                    "composite_score": top_c.composite_score,
                    "tactical_fit": top_c.tactical_fit_score,
                    "xtv_growth": top_c.xtv_growth_score,
                    "profile_url": top_c.data_citation_url,
                    "sensitivity": solution.sensitivity.model_dump()
                },
                estimated_cost=1800.0,
                impact_level="MEDIUM"
            )
            h_duration = (time.time() - h_start) * 1000.0

            tool_records.append(
                ToolExecutionRecord(
                    tool_name="stage_hitl_action",
                    arguments={"action_type": "ACTION_DISPATCH_SCOUT", "player": top_c.name},
                    duration_ms=round(h_duration, 2),
                    status="SUCCESS",
                    output_summary=f"Staged action {staged_action.action_id} in approval queue (status: PENDING)."
                )
            )

        elapsed_ms = (time.time() - start_time) * 1000.0
        decision_summary = (
            f"Optimized recruitment recommendation for '{user_query}'. "
            f"Selected {len(solution.candidates)} candidates. Top recommendation: "
            f"'{solution.candidates[0].name if solution.candidates else 'N/A'}' with composite score "
            f"{solution.candidates[0].composite_score if solution.candidates else 0:.1f} and "
            f"{solution.model_confidence_score * 100:.0f}% confidence."
        )

        # Step 4: Observability Trace Logging
        trace = self.tracker.log_run(
            trigger_type=trigger_type,
            query=user_query,
            phase="DECISION_SOLVE_AND_STAGE",
            tool_calls=tool_records,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_comp_tokens,
            model_name=self.model_name,
            execution_time_ms=elapsed_ms,
            status="SUCCESS",
            decision_summary=decision_summary,
            run_id=run_id
        )

        return {
            "run_id": run_id,
            "status": solution.status,
            "formalized_spec": spec.model_dump(),
            "solution": solution.model_dump(),
            "staged_hitl_action": staged_action.model_dump() if staged_action else None,
            "observability_trace": trace.model_dump(),
            "execution_time_ms": round(elapsed_ms, 2)
        }
