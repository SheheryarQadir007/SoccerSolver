"""
SoccerSolver - Test Suite: Human in the Loop (HITL) Queue & Safety Checks
Validates Rule: Irreversible actions NEVER run without explicit human approval.
"""

import pytest
from soccersolver.hitl.queue import ActionQueue, IrreversibleActionRequiresApprovalError
from soccersolver.hitl.models import ActionType, ActionStatus, ActionReviewInput


def test_stage_and_approve_action():
    queue = ActionQueue()
    action = queue.stage_action(
        action_type=ActionType.DISPATCH_SCOUT,
        player_id=12345,
        player_name="Test Candidate",
        target_club="Real Betis",
        summary="Test scout dispatch",
        payload={"notes": "Scout test"}
    )
    assert action.status == ActionStatus.PENDING

    # Review: Approve
    reviewed = queue.review_action(action.action_id, ActionReviewInput(decision="APPROVE", reviewer_notes="Looks solid"))
    assert reviewed.status == ActionStatus.APPROVED
    assert "Dispatched" in reviewed.execution_result


def test_irreversible_action_blocks_unauthorized_execution():
    queue = ActionQueue()
    # Staging an irreversible offer action
    action = queue.stage_action(
        action_type=ActionType.SUBMIT_OFFER,
        player_id=99999,
        player_name="High Value Star",
        target_club="Valencia CF",
        summary="Submit €2.5M formal offer",
        payload={"proposed_fee_eur": 2500000.0}
    )
    assert action.is_irreversible is True
    assert action.status == ActionStatus.PENDING

    # Autonomous execution MUST be blocked and raise IrreversibleActionRequiresApprovalError!
    with pytest.raises(IrreversibleActionRequiresApprovalError):
        queue.attempt_autonomous_execution(action.action_id)

    # Now approve it
    queue.review_action(action.action_id, ActionReviewInput(decision="APPROVE", reviewer_notes="Approved by Sporting Director"))
    
    # After approval, autonomous execution succeeds
    res = queue.attempt_autonomous_execution(action.action_id)
    assert "Transfer Offer Submitted" in res
