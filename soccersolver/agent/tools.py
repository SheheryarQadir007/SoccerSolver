"""
SoccerSolver - Agent Tool Definitions (MCP / Function-Calling Compliant)
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from soccersolver.data.repository import FootballDataRepository
from soccersolver.optimization.formalizer import ProblemFormalizer
from soccersolver.optimization.solver import MathematicalOptimizationSolver
from soccersolver.optimization.models import OptimizationSpec
from soccersolver.backtest.engine import BacktestEngine
from soccersolver.hitl.queue import ActionQueue
from soccersolver.hitl.models import ActionType


class AgentToolRegistry:
    def __init__(
        self,
        repo: Optional[FootballDataRepository] = None,
        formalizer: Optional[ProblemFormalizer] = None,
        solver: Optional[MathematicalOptimizationSolver] = None,
        backtester: Optional[BacktestEngine] = None,
        queue: Optional[ActionQueue] = None
    ):
        self.repo = repo or FootballDataRepository()
        self.formalizer = formalizer or ProblemFormalizer()
        self.solver = solver or MathematicalOptimizationSolver(self.repo)
        self.backtester = backtester or BacktestEngine(self.repo)
        self.queue = queue or ActionQueue()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns standard JSON schemas for all agent tools."""
        return [
            {
                "name": "formalize_scouting_problem",
                "description": "Translates natural language recruitment goals into a formal mathematical optimization specification.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "natural_language_query": {"type": "string", "description": "User description of recruitment target."}
                    },
                    "required": ["natural_language_query"]
                }
            },
            {
                "name": "query_football_database",
                "description": "Retrieves real verified player data, market values, and appearances from SQLite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sub_position": {"type": "string"},
                        "max_budget_eur": {"type": "number"},
                        "max_age": {"type": "integer"},
                        "min_minutes": {"type": "integer"}
                    }
                }
            },
            {
                "name": "solve_mathematical_optimization",
                "description": "Executes TOPSIS multi-criteria solver, Pareto frontier identification, and sensitivity analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "spec": {"type": "object", "description": "OptimizationSpec dictionary."}
                    },
                    "required": ["spec"]
                }
            },
            {
                "name": "run_historical_backtest",
                "description": "Simulates recommendations on a past season and measures ground-truth forward realized valuation and ROI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "historical_season": {"type": "string", "enum": ["2021/2022", "2022/2023", "2023/2024"]},
                        "position": {"type": "string"},
                        "budget": {"type": "number"}
                    },
                    "required": ["historical_season", "position"]
                }
            },
            {
                "name": "stage_hitl_action",
                "description": "Stages a high-impact or irreversible action into the Human-in-the-Loop review queue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_type": {"type": "string", "enum": [e.value for e in ActionType]},
                        "player_id": {"type": "integer"},
                        "player_name": {"type": "string"},
                        "target_club": {"type": "string"},
                        "summary": {"type": "string"},
                        "payload": {"type": "object"}
                    },
                    "required": ["action_type", "player_id", "player_name", "target_club", "summary"]
                }
            }
        ]
