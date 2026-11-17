"""
SoccerSolver - Command Line Interface (CLI)
Provides comprehensive terminal access to the decision-making agent.
"""

import sys
import click
import uvicorn
from soccersolver.agent.orchestrator import DecisionMakingAgent
from soccersolver.backtest.engine import BacktestEngine
from soccersolver.hitl.queue import ActionQueue
from soccersolver.hitl.models import ActionReviewInput
from soccersolver.proactive.triggers import ProactiveEventEngine
from soccersolver.observability.tracker import ObservabilityTracker


@click.group()
def cli():
    """SoccerSolver - Autonomous Football Intelligence & Decision Engine"""
    pass


@cli.command()
@click.argument("query", default="we need a left back under 3M€ who fits LaLiga")
@click.option("--no-hitl", is_flag=True, help="Disable auto-staging into HITL queue")
def solve(query: str, no_hitl: bool):
    """Formalize and solve a natural language recruitment problem."""
    click.secho("\n⚽ SoccerSolver Decision-Making Agent", fg="green", bold=True)
    click.secho(f"Query: \"{query}\"\n", fg="cyan")

    agent = DecisionMakingAgent()
    result = agent.process_recruitment_query(user_query=query, auto_stage_hitl=not no_hitl)

    sol = result["solution"]
    sens = sol["sensitivity"]

    click.secho(f"Status: {sol['status']} (Solved in {sol['execution_time_ms']} ms | Confidence: {sol['model_confidence_score']*100:.0f}%)", fg="green")
    click.secho(f"Slack Capital: €{sens['slack_budget_eur']:,.0f} | Shadow Price (+15% budget): +{sens['budget_shadow_price_pct']}%", fg="yellow")
    click.secho(f"Trade-off Insight: {sens['tradeoff_notes']}\n", fg="white")

    click.secho("Top Mathematically Optimal Candidates (Verified Real Data):", fg="green", bold=True)
    for c in sol["candidates"][:5]:
        click.secho(
            f"#{c['rank']} {c['name']} ({c['age']}y) | Club: {c['current_club_name']} ({c['current_league_code']})\n"
            f"   Valuation: €{c['market_value_eur']:,.0f} | Score: {c['composite_score']} | Tactical Fit: {c['tactical_fit_score']} | xGrowth: {c['xtv_growth_score']}\n"
            f"   Confidence: {c['confidence_level']*100:.0f}% | Citation: {c['data_citation_url']}",
            fg="white"
        )
        if c.get("data_disagreement_notes"):
            click.secho(f"   Note: {c['data_disagreement_notes']}", fg="bright_black")
        click.echo("")

    if result.get("staged_hitl_action"):
        act = result["staged_hitl_action"]
        click.secho("Human-in-the-Loop Action Staged:", fg="yellow", bold=True)
        click.secho(f"   ID: {act['action_id']} | Type: {act['action_type']} | Status: {act['status']}", fg="yellow")
        click.secho(f"   Summary: {act['summary']}\n", fg="white")


@cli.command()
@click.option("--season", default="2022/2023", help="Historical cutoff season (2021/2022, 2022/2023, 2023/2024)")
@click.option("--position", default="Left-Back", help="Position specification")
@click.option("--budget", default=3000000.0, type=float, help="Historical budget cap in EUR")
@click.option("--top-k", default=5, type=int, help="Number of recommendations to evaluate")
def backtest(season: str, position: str, budget: float, top_k: int):
    """Run historical backtest against ground-truth forward valuation outcomes."""
    click.secho(f"\n📊 Historical Backtesting Engine [{season}]", fg="cyan", bold=True)
    engine = BacktestEngine()
    rep = engine.run_backtest(historical_season=season, position=position, budget=budget, top_k=top_k)

    click.secho(f"Screened Candidates: {rep.total_candidates_screened} | Portfolio Hit Rate: {rep.portfolio_hit_rate_pct}%", fg="green")
    click.secho(f"Average Value Growth: +{rep.average_value_appreciation_pct}% | Unrealized Capital Gain: €{rep.total_unrealized_profit_eur:,.0f}", fg="green")
    click.secho(f"ROI Multiple: {rep.roi_multiple}x | Sharpe Proxy: {rep.sharpe_proxy_ratio}\n", fg="yellow")
    click.secho(f"Benchmark: {rep.benchmark_note}\n", fg="bright_black")

    click.secho("Realized Recommendations:", fg="cyan", bold=True)
    for r in rep.top_recommendations:
        sign = "+" if r.percentage_growth >= 0 else ""
        click.secho(
            f"#{r.rank} {r.name} | Entry: €{r.entry_market_value_eur:,.0f} -> Realized: €{r.forward_market_value_eur:,.0f} ({sign}{r.percentage_growth:.1f}%)\n"
            f"   Verdict: {r.verdict} | Profile: {r.historical_profile_url}",
            fg="white"
        )


@cli.command()
@click.option("--event", type=click.Choice(["injury", "expiry"]), default="injury")
@click.option("--club", default="Getafe CF")
@click.option("--injured", default="Diego Rico")
@click.option("--position", default="Left-Back")
@click.option("--budget", default=3000000.0, type=float)
def trigger(event: str, club: str, injured: str, position: str, budget: float):
    """Simulate proactive event bus triggers."""
    engine = ProactiveEventEngine()
    if event == "injury":
        click.secho(f"🚨 Firing Proactive Injury Event: {injured} ({club})", fg="red", bold=True)
        res = engine.handle_injury_event(club_name=club, injured_player_name=injured, position=position, budget_eur=budget)
        click.secho(f"Optimal Emergency Replacement: {res['top_candidate']}", fg="green")
        click.secho(f"Staged Actions in Queue: {res['staged_actions']}", fg="yellow")
    else:
        click.secho("⚡ Running Proactive Expiration Leverage Scan...", fg="yellow", bold=True)
        deals = engine.scan_contract_expiry_opportunities(max_budget=budget, limit=3)
        click.secho(f"Identified and staged {len(deals)} expiring contract opportunities.", fg="green")
        for d in deals:
            click.echo(f" - {d['name']} ({d['club']}) | Exp: {d['contract_expiration'][:10]} | Val: €{d['market_value']:,.0f}")


@cli.group()
def queue():
    """Human-in-the-Loop action queue management."""
    pass


@queue.command("list")
def queue_list():
    """List pending and reviewed actions in the HITL queue."""
    q = ActionQueue()
    actions = q.list_actions()
    click.secho(f"\n📋 HITL Action Queue ({len(actions)} total actions):", fg="cyan", bold=True)
    for a in actions:
        irrev = "[IRREVERSIBLE]" if a.is_irreversible else ""
        click.secho(f"[{a.status.value}] {a.action_id} {irrev} - {a.summary}", fg="yellow" if a.status.value == "PENDING" else "white")
        if a.execution_result:
            click.secho(f"   Execution: {a.execution_result}", fg="green")


@queue.command("approve")
@click.argument("action_id")
@click.option("--notes", default="Approved by Sporting Director.")
def queue_approve(action_id: str, notes: str):
    """Approve a proposed action and execute it."""
    q = ActionQueue()
    try:
        act = q.review_action(action_id, ActionReviewInput(decision="APPROVE", reviewer_notes=notes))
        click.secho(f"✅ Action {action_id} APPROVED.", fg="green", bold=True)
        click.secho(f"Result: {act.execution_result}", fg="white")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")


@queue.command("reject")
@click.argument("action_id")
@click.option("--reason", default="Rejected by Sporting Director.")
def queue_reject(action_id: str, reason: str):
    """Reject a proposed action."""
    q = ActionQueue()
    try:
        act = q.review_action(action_id, ActionReviewInput(decision="REJECT", reviewer_notes=reason))
        click.secho(f"❌ Action {action_id} REJECTED.", fg="yellow", bold=True)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")


@cli.command()
def logs():
    """Display observability traces and token/USD cost metrics."""
    tracker = ObservabilityTracker()
    summary = tracker.get_summary_metrics()
    click.secho("\n📈 Observability & Cost Summary:", fg="cyan", bold=True)
    click.secho(f"Total Runs: {summary['total_runs']} | Total Prompt Tokens: {summary['total_prompt_tokens']:,}", fg="white")
    click.secho(f"Total USD Cost: ${summary['total_cost_usd']:.5f} | Average Latency: {summary['avg_latency_ms']} ms\n", fg="green")

    traces = tracker.get_traces(limit=10)
    for t in traces:
        click.secho(f"[{t.timestamp[11:19]}] {t.run_id} | {t.trigger_type} | {t.execution_time_ms} ms | ${t.estimated_cost_usd:.5f}", fg="yellow")
        click.secho(f"   Query: {t.query}", fg="white")
        click.secho(f"   Decision: {t.decision_summary}", fg="bright_black")


@cli.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8000, type=int)
def web(host: str, port: int):
    """Launch the interactive web Control Panel."""
    click.secho(f"\n🚀 Starting SoccerSolver Control Panel at http://{host}:{port}", fg="green", bold=True)
    uvicorn.run("soccersolver.server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    cli()
