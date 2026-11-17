"""
SoccerSolver - Observability & Cost Tracking Engine
Logs every agent decision, tool execution, token usage, and computes USD cost per run.
"""

import json
import sqlite3
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from soccersolver.config import DB_PATH, TOKEN_PRICING


class ToolExecutionRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    duration_ms: float
    status: str = "SUCCESS"
    output_summary: str


class ObservabilityTrace(BaseModel):
    run_id: str
    timestamp: str
    trigger_type: str  # USER_QUERY, PROACTIVE_EVENT, SCHEDULED_CRON
    query: str
    phase: str
    tool_calls: List[ToolExecutionRecord] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model_name: str = "gemini-2.0-flash"
    estimated_cost_usd: float = 0.0
    execution_time_ms: float = 0.0
    status: str = "SUCCESS"
    decision_summary: str = ""


class ObservabilityTracker:
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
                CREATE TABLE IF NOT EXISTS observability_traces (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    query TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    tool_calls TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    status TEXT NOT NULL,
                    decision_summary TEXT
                );
            """)
            conn.commit()

    def calculate_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = TOKEN_PRICING.get(model_name, TOKEN_PRICING["gemini-2.0-flash"])
        p_cost = (prompt_tokens / 1_000_000.0) * pricing["prompt_per_1m"]
        c_cost = (completion_tokens / 1_000_000.0) * pricing["completion_per_1m"]
        return round(p_cost + c_cost, 6)

    def log_run(
        self,
        trigger_type: str,
        query: str,
        phase: str,
        tool_calls: List[ToolExecutionRecord],
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
        execution_time_ms: float,
        status: str = "SUCCESS",
        decision_summary: str = "",
        run_id: Optional[str] = None
    ) -> ObservabilityTrace:
        rid = run_id or f"RUN-{str(uuid.uuid4())[:8].upper()}"
        cost = self.calculate_cost(model_name, prompt_tokens, completion_tokens)
        ts = datetime.now().isoformat()

        trace = ObservabilityTrace(
            run_id=rid,
            timestamp=ts,
            trigger_type=trigger_type,
            query=query,
            phase=phase,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model_name=model_name,
            estimated_cost_usd=cost,
            execution_time_ms=round(execution_time_ms, 2),
            status=status,
            decision_summary=decision_summary
        )

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO observability_traces (
                    run_id, timestamp, trigger_type, query, phase,
                    tool_calls, prompt_tokens, completion_tokens, model_name,
                    estimated_cost_usd, execution_time_ms, status, decision_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trace.run_id,
                trace.timestamp,
                trace.trigger_type,
                trace.query,
                trace.phase,
                json.dumps([t.model_dump() for t in trace.tool_calls]),
                trace.prompt_tokens,
                trace.completion_tokens,
                trace.model_name,
                trace.estimated_cost_usd,
                trace.execution_time_ms,
                trace.status,
                trace.decision_summary
            ))
            conn.commit()

        return trace

    def get_traces(self, limit: int = 50) -> List[ObservabilityTrace]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM observability_traces ORDER BY timestamp DESC LIMIT ?", (limit,))
            traces = []
            for r in cur.fetchall():
                calls = [ToolExecutionRecord(**t) for t in json.loads(r["tool_calls"])]
                traces.append(ObservabilityTrace(
                    run_id=r["run_id"],
                    timestamp=r["timestamp"],
                    trigger_type=r["trigger_type"],
                    query=r["query"],
                    phase=r["phase"],
                    tool_calls=calls,
                    prompt_tokens=r["prompt_tokens"],
                    completion_tokens=r["completion_tokens"],
                    model_name=r["model_name"],
                    estimated_cost_usd=r["estimated_cost_usd"],
                    execution_time_ms=r["execution_time_ms"],
                    status=r["status"],
                    decision_summary=r["decision_summary"]
                ))
            return traces

    def get_summary_metrics(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) as total_runs,
                       COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) as total_comp_tokens,
                       COALESCE(SUM(estimated_cost_usd), 0.0) as total_cost,
                       COALESCE(AVG(execution_time_ms), 0.0) as avg_latency_ms
                FROM observability_traces
            """)
            r = cur.fetchone()
            return {
                "total_runs": r["total_runs"],
                "total_prompt_tokens": r["total_prompt_tokens"],
                "total_completion_tokens": r["total_comp_tokens"],
                "total_cost_usd": round(r["total_cost"], 5),
                "avg_latency_ms": round(r["avg_latency_ms"], 1)
            }
