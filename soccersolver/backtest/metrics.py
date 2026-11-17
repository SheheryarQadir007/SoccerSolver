"""
SoccerSolver - Backtest Metrics and Evaluation Models
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class BacktestCandidateOutcome(BaseModel):
    rank: int
    player_id: int
    name: str
    entry_date: str
    entry_market_value_eur: float
    forward_market_value_eur: float
    value_delta_eur: float
    percentage_growth: float
    is_success: bool
    subsequent_transfer_fee: Optional[float] = None
    subsequent_club: Optional[str] = None
    historical_profile_url: str
    verdict: str


class BacktestReport(BaseModel):
    test_id: str
    historical_season: str
    cutoff_date: str
    position: str
    budget_limit_eur: float
    total_candidates_screened: int
    top_recommendations: List[BacktestCandidateOutcome]
    
    # Portfolio Aggregate Metrics
    portfolio_hit_rate_pct: float = Field(..., description="% of recommended players that appreciated in value")
    average_value_appreciation_pct: float = Field(..., description="Mean percentage xTV growth across recommendations")
    total_unrealized_profit_eur: float = Field(..., description="Total capital gain across portfolio (€)")
    roi_multiple: float = Field(..., description="Forward valuation / Entry cost ratio")
    sharpe_proxy_ratio: float = Field(..., description="Risk-adjusted return multiple")
    
    # Counterfactual comparison
    benchmark_note: str = Field(..., description="Comparison against average market benchmark during the same window")
    model_calibration_confidence: float = Field(..., description="Statistical confidence in recommendation calibration")
