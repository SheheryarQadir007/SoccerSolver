"""
SoccerSolver - Human in the Loop (HITL) Action Models
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    DISPATCH_SCOUT = "ACTION_DISPATCH_SCOUT"
    CONTACT_AGENCY = "ACTION_CONTACT_AGENCY"
    SUBMIT_OFFER = "ACTION_SUBMIT_OFFER"
    GENERATE_BOARD_DOSSIER = "ACTION_GENERATE_BOARD_DOSSIER"


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class ProposedAction(BaseModel):
    action_id: str
    action_type: ActionType
    player_id: int
    player_name: str
    target_club: str
    summary: str
    detailed_payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Risk & Irreversibility
    is_irreversible: bool = Field(default=False, description="True for external outreach or financial commitments")
    estimated_cost_eur: float = 0.0
    impact_level: str = "MEDIUM" # LOW, MEDIUM, HIGH, CRITICAL

    # State & Audit
    status: ActionStatus = ActionStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    reviewed_at: Optional[str] = None
    reviewer_notes: Optional[str] = None
    execution_result: Optional[str] = None


class ActionReviewInput(BaseModel):
    decision: str = Field(..., description="'APPROVE', 'EDIT', or 'REJECT'")
    reviewer_notes: Optional[str] = None
    edited_payload: Optional[Dict[str, Any]] = None
