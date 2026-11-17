"""
SoccerSolver - Optimization Data Models
Pydantic schemas for formalizing recruitment problems into strict mathematical programs.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ConstraintType(str, Enum):
    LEQ = "<="
    GEQ = ">="
    EQ = "=="
    IN = "in"


class MathematicalConstraint(BaseModel):
    variable: str = Field(..., description="Target attribute (e.g. market_value_in_eur, age, minutes_played)")
    operator: ConstraintType = Field(..., description="Inequality or inclusion operator")
    value: Any = Field(..., description="Threshold value or list of allowed values")
    human_description: str = Field(..., description="Readable explanation of the constraint")
    is_hard: bool = Field(default=True, description="Whether constraint is non-negotiable")


class ObjectiveWeights(BaseModel):
    tactical_fit: float = Field(default=0.45, description="Weight for tactical / style fit to target league")
    expected_growth_xtv: float = Field(default=0.30, description="Weight for projected value appreciation (xTV gain)")
    value_efficiency: float = Field(default=0.15, description="Weight for performance per euro spent")
    age_potential: float = Field(default=0.10, description="Weight for younger age profile / resale window")
    financial_risk_penalty: float = Field(default=0.10, description="Risk penalty coefficient lambda")
    profile_similarity: float = Field(default=0.0, description="Weight for similarity to reference player if specified")


class OptimizationSpec(BaseModel):
    problem_id: str
    query_natural_language: str
    target_position: str
    allowed_sub_positions: List[str] = Field(default_factory=list)
    target_league_code: str = Field(default="ES1", description="Competition ID, e.g. ES1 for La Liga, GB1 for Premier League")
    max_budget_eur: float
    max_age: Optional[int] = None
    min_minutes_played: int = Field(default=450, description="Minimum sample size of minutes for statistical confidence")
    constraints: List[MathematicalConstraint] = Field(default_factory=list)
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    preferred_foot: Optional[str] = None
    reference_player_name: Optional[str] = None
    reference_player_id: Optional[int] = None
    reference_tactical_vector: Optional[Dict[str, float]] = None
    mathematical_formulation_latex: str = Field(
        default="",
        description="LaTeX representation of the formal optimization problem for report/UI"
    )


class SensitivityAnalysis(BaseModel):
    budget_shadow_price_pct: float = Field(
        ...,
        description="Estimated % gain in top candidate score if budget is relaxed by 15%"
    )
    budget_elasticity: float = Field(
        ...,
        description="Candidate quality score change per 100k EUR"
    )
    slack_budget_eur: float = Field(
        ...,
        description="Unspent budget of the top selected candidate"
    )
    binding_constraints: List[str] = Field(
        default_factory=list,
        description="Constraints that currently restrict better candidates"
    )
    tradeoff_notes: str = Field(
        ...,
        description="Actionable explanation of financial vs tactical trade-offs"
    )


class CandidateResult(BaseModel):
    rank: int
    player_id: int
    name: str
    age: int
    current_club_name: str
    current_league_code: str
    position: str
    sub_position: str
    market_value_eur: float
    estimated_transfer_fee: float
    contract_expiration_date: Optional[str]
    minutes_played_recent: int
    data_source: str
    data_citation_url: str

    # Optimization Scores (0-100)
    composite_score: float
    tactical_fit_score: float
    xtv_growth_score: float
    value_efficiency_score: float
    similarity_to_reference: Optional[float] = None

    # Statistical Metrics
    confidence_level: float = Field(..., description="Statistical confidence based on minutes sample & variance (0.0 - 1.0)")
    league_adaptation_factor: float
    decision_rationale: str
    data_disagreement_notes: Optional[str] = None


class OptimizationSolution(BaseModel):
    spec: OptimizationSpec
    solver_algorithm: str = "Multi-Criteria Decision Analysis (TOPSIS) + Mixed-Integer Filtering"
    status: str = "OPTIMAL"
    candidates: List[CandidateResult]
    sensitivity: SensitivityAnalysis
    execution_time_ms: float
    model_confidence_score: float
