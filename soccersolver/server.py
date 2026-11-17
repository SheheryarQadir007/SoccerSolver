"""
SoccerSolver - FastAPI Server and API Endpoints
Provides REST API and Interactive Web Control Panel.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from soccersolver.config import DB_PATH
from soccersolver.data.repository import FootballDataRepository
from soccersolver.agent.orchestrator import DecisionMakingAgent
from soccersolver.backtest.engine import BacktestEngine
from soccersolver.hitl.queue import ActionQueue, IrreversibleActionRequiresApprovalError
from soccersolver.hitl.models import ActionReviewInput, ActionStatus
from soccersolver.proactive.triggers import ProactiveEventEngine
from soccersolver.proactive.scheduler import ProactiveScheduler
from soccersolver.observability.tracker import ObservabilityTracker

app = FastAPI(
    title="SoccerSolver Solution Agent",
    description="AI-powered player valuation and mathematical recruitment optimization engine.",
    version="1.0.0"
)

TEMPLATES_DIR = Path(__file__).parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize services
repo = FootballDataRepository()
agent = DecisionMakingAgent(repo=repo)
backtester = BacktestEngine(repo=repo)
queue = ActionQueue()
proactive_engine = ProactiveEventEngine(repo=repo, queue=queue)
scheduler = ProactiveScheduler(engine=proactive_engine)
tracker = ObservabilityTracker()


# --- Pydantic Request Models ---
class SolveQueryRequest(BaseModel):
    query: str
    auto_stage_hitl: bool = True


class BacktestRequest(BaseModel):
    historical_season: str = "2022/2023"
    position: str = "Left-Back"
    budget: float = 3_000_000.0
    top_k: int = 10


class ReviewActionRequest(BaseModel):
    decision: str  # APPROVE, EDIT, REJECT
    reviewer_notes: Optional[str] = None
    edited_payload: Optional[Dict[str, Any]] = None


class TriggerInjuryRequest(BaseModel):
    club_name: str = "Getafe CF"
    injured_player_name: str = "Diego Rico"
    position: str = "Left-Back"
    budget_eur: float = 3_000_000.0


# --- Web Page Route ---
@app.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# --- API Routes ---
@app.post("/api/solve")
async def api_solve(req: SolveQueryRequest):
    try:
        result = agent.process_recruitment_query(
            user_query=req.query,
            auto_stage_hitl=req.auto_stage_hitl
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backtest")
async def api_backtest(req: BacktestRequest):
    try:
        report = backtester.run_backtest(
            historical_season=req.historical_season,
            position=req.position,
            budget=req.budget,
            top_k=req.top_k
        )
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hitl/actions")
async def api_list_actions(status: Optional[str] = None):
    s_enum = ActionStatus(status) if status else None
    actions = queue.list_actions(status=s_enum)
    return [a.model_dump() for a in actions]


@app.post("/api/hitl/actions/{action_id}/review")
async def api_review_action(action_id: str, review: ReviewActionRequest):
    try:
        inp = ActionReviewInput(
            decision=review.decision,
            reviewer_notes=review.reviewer_notes,
            edited_payload=review.edited_payload
        )
        action = queue.review_action(action_id, inp)
        return action.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="Action not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/proactive/trigger-injury")
async def api_trigger_injury(req: TriggerInjuryRequest):
    res = proactive_engine.handle_injury_event(
        club_name=req.club_name,
        injured_player_name=req.injured_player_name,
        position=req.position,
        budget_eur=req.budget_eur
    )
    return res


@app.post("/api/proactive/scan-expirations")
async def api_scan_expirations():
    deals = proactive_engine.scan_contract_expiry_opportunities(limit=3)
    return {"status": "SUCCESS", "scanned_deals_count": len(deals), "deals": deals}


@app.get("/api/observability/traces")
async def api_get_traces(limit: int = 50):
    traces = tracker.get_traces(limit=limit)
    return [t.model_dump() for t in traces]


@app.get("/api/observability/metrics")
async def api_get_metrics():
    return tracker.get_summary_metrics()


@app.get("/api/data/stats")
async def api_data_stats():
    import sqlite3
    with sqlite3.connect(str(DB_PATH)) as conn:
        cur = conn.cursor()
        counts = {}
        for table in ["players", "clubs", "competitions", "player_valuations", "transfers"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]
    return {
        "database_file": str(DB_PATH),
        "source": "Transfermarkt Open Datasets (dcaribou/transfermarkt-datasets, ODbL)",
        "record_counts": counts
    }


@app.get("/api/data/players")
async def api_search_players(
    search: Optional[str] = None,
    position: Optional[str] = None,
    league: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    offset = max(0, (page - 1) * page_size)
    players, total = repo.search_players_paginated(
        search=search,
        position=position,
        league=league,
        offset=offset,
        limit=page_size
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "players": players
    }
