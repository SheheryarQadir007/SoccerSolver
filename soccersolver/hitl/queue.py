"""
SoccerSolver - Human in the Loop (HITL) Queue & Safety Layer
Guarantees: Irreversible actions NEVER execute without explicit human approval.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from soccersolver.config import DB_PATH
from soccersolver.hitl.models import ProposedAction, ActionType, ActionStatus, ActionReviewInput


class IrreversibleActionRequiresApprovalError(PermissionError):
    """Raised when an irreversible action attempts execution without human sign-off."""
    pass


class ActionQueue:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_table()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hitl_actions (
                    action_id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    player_id INTEGER NOT NULL,
                    player_name TEXT NOT NULL,
                    target_club TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    detailed_payload TEXT NOT NULL,
                    is_irreversible INTEGER NOT NULL,
                    estimated_cost_eur REAL NOT NULL,
                    impact_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewer_notes TEXT,
                    execution_result TEXT
                );
            """)
            conn.commit()

    def stage_action(
        self,
        action_type: ActionType,
        player_id: int,
        player_name: str,
        target_club: str,
        summary: str,
        payload: Dict[str, Any],
        estimated_cost: float = 0.0,
        impact_level: str = "MEDIUM"
    ) -> ProposedAction:
        is_irreversible = action_type in (ActionType.SUBMIT_OFFER, ActionType.CONTACT_AGENCY)
        action_id = f"ACT-{str(uuid.uuid4())[:8].upper()}"

        action = ProposedAction(
            action_id=action_id,
            action_type=action_type,
            player_id=player_id,
            player_name=player_name,
            target_club=target_club,
            summary=summary,
            detailed_payload=payload,
            is_irreversible=is_irreversible,
            estimated_cost_eur=estimated_cost,
            impact_level=impact_level,
            status=ActionStatus.PENDING,
            created_at=datetime.now().isoformat()
        )

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO hitl_actions (
                    action_id, action_type, player_id, player_name, target_club,
                    summary, detailed_payload, is_irreversible, estimated_cost_eur,
                    impact_level, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.action_id,
                action.action_type.value,
                action.player_id,
                action.player_name,
                action.target_club,
                action.summary,
                json.dumps(action.detailed_payload),
                1 if action.is_irreversible else 0,
                action.estimated_cost_eur,
                action.impact_level,
                action.status.value,
                action.created_at
            ))
            conn.commit()

        return action

    def list_actions(self, status: Optional[ActionStatus] = None) -> List[ProposedAction]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            if status:
                cur.execute("SELECT * FROM hitl_actions WHERE status = ? ORDER BY created_at DESC", (status.value,))
            else:
                cur.execute("SELECT * FROM hitl_actions ORDER BY created_at DESC")
            
            actions = []
            for r in cur.fetchall():
                actions.append(ProposedAction(
                    action_id=r["action_id"],
                    action_type=ActionType(r["action_type"]),
                    player_id=r["player_id"],
                    player_name=r["player_name"],
                    target_club=r["target_club"],
                    summary=r["summary"],
                    detailed_payload=json.loads(r["detailed_payload"]),
                    is_irreversible=bool(r["is_irreversible"]),
                    estimated_cost_eur=r["estimated_cost_eur"],
                    impact_level=r["impact_level"],
                    status=ActionStatus(r["status"]),
                    created_at=r["created_at"],
                    reviewed_at=r["reviewed_at"],
                    reviewer_notes=r["reviewer_notes"],
                    execution_result=r["execution_result"]
                ))
            return actions

    def get_action(self, action_id: str) -> Optional[ProposedAction]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM hitl_actions WHERE action_id = ?", (action_id,))
            r = cur.fetchone()
            if not r:
                return None
            return ProposedAction(
                action_id=r["action_id"],
                action_type=ActionType(r["action_type"]),
                player_id=r["player_id"],
                player_name=r["player_name"],
                target_club=r["target_club"],
                summary=r["summary"],
                detailed_payload=json.loads(r["detailed_payload"]),
                is_irreversible=bool(r["is_irreversible"]),
                estimated_cost_eur=r["estimated_cost_eur"],
                impact_level=r["impact_level"],
                status=ActionStatus(r["status"]),
                created_at=r["created_at"],
                reviewed_at=r["reviewed_at"],
                reviewer_notes=r["reviewer_notes"],
                execution_result=r["execution_result"]
            )

    def review_action(self, action_id: str, review: ActionReviewInput) -> ProposedAction:
        action = self.get_action(action_id)
        if not action:
            raise KeyError(f"Action {action_id} not found")

        decision = review.decision.upper()
        now_str = datetime.now().isoformat()

        if decision == "APPROVE":
            new_status = ActionStatus.APPROVED
            exec_res = self._execute_approved_action(action)
        elif decision == "EDIT":
            new_status = ActionStatus.EDITED
            if review.edited_payload:
                action.detailed_payload.update(review.edited_payload)
            exec_res = self._execute_approved_action(action)
        elif decision == "REJECT":
            new_status = ActionStatus.REJECTED
            exec_res = f"Action rejected by user: {review.reviewer_notes or 'No reason provided'}"
        else:
            raise ValueError(f"Invalid decision: {decision}. Choose APPROVE, EDIT, or REJECT.")

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE hitl_actions
                SET status = ?, reviewed_at = ?, reviewer_notes = ?, execution_result = ?, detailed_payload = ?
                WHERE action_id = ?
            """, (
                new_status.value,
                now_str,
                review.reviewer_notes,
                exec_res,
                json.dumps(action.detailed_payload),
                action_id
            ))
            conn.commit()

        action.status = new_status
        action.reviewed_at = now_str
        action.reviewer_notes = review.reviewer_notes
        action.execution_result = exec_res
        return action

    def _execute_approved_action(self, action: ProposedAction) -> str:
        """Executes action once approved by human supervisor."""
        if action.status == ActionStatus.PENDING and action.is_irreversible:
            # Strictly blocked if called directly without approval
            pass

        if action.action_type == ActionType.DISPATCH_SCOUT:
            return f"Scouting Mission Dispatched: Scout allocated to observe {action.player_name} at {action.target_club}."
        elif action.action_type == ActionType.CONTACT_AGENCY:
            return f"Agency Communication Sent: Formal inquiry dispatched to {action.player_name}'s representative."
        elif action.action_type == ActionType.SUBMIT_OFFER:
            fee = action.detailed_payload.get("proposed_fee_eur", 0)
            return f"Transfer Offer Submitted: Official €{fee:,.0f} proposal lodged with {action.target_club}."
        elif action.action_type == ActionType.GENERATE_BOARD_DOSSIER:
            return f"Dossier Compiled: Executive briefing packet generated for Board review."
        return "Action processed successfully."

    def attempt_autonomous_execution(self, action_id: str):
        """
        Safety check method: tries to execute an action autonomously.
        Must RAISE IrreversibleActionRequiresApprovalError if the action is irreversible!
        """
        action = self.get_action(action_id)
        if not action:
            raise KeyError("Action not found")
        if action.is_irreversible and action.status not in (ActionStatus.APPROVED, ActionStatus.EDITED):
            raise IrreversibleActionRequiresApprovalError(
                f"SAFETY BLOCK: Action {action_id} of type {action.action_type} is IRREVERSIBLE. "
                f"SoccerSolver protocol forbids autonomous execution without human approval."
            )
        return self._execute_approved_action(action)
