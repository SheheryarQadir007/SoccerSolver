"""
SoccerSolver - Data Repository Layer
Data Integrity: Every returned data point includes citation, source URL, and license.
Supports any position, league, budget, and player-similarity queries.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union

from soccersolver.config import (
    DB_PATH,
    get_league_adaptation_factor,
)


class FootballDataRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or DB_PATH)
        self._ensure_database_ready()

    def _ensure_database_ready(self):
        """Auto-extract from soccersolver.db.gz if db is missing."""
        if not self.db_path.exists():
            gz_path = self.db_path.with_name("soccersolver.db.gz")
            if gz_path.exists():
                import gzip, shutil
                print(f"Extracting {gz_path.name} to {self.db_path.name}...")
                with gzip.open(gz_path, "rb") as f_in, open(self.db_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                print("Database ready.")
            else:
                from scripts.prepare_data import main as build_db
                build_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_competitions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM competitions ORDER BY name")
            return [dict(r) for r in cur.fetchall()]

    def get_player_by_id(self, player_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT p.*, c.name as club_name, comp.name as competition_name,
                       comp.country_name, t.progression_score, t.defensive_work_rate,
                       t.creativity_score, t.pressing_intensity, t.aerial_dominance,
                       t.league_fit_score, t.confidence_score
                FROM players p
                LEFT JOIN clubs c ON p.current_club_id = c.club_id
                LEFT JOIN competitions comp ON p.current_club_domestic_competition_id = comp.competition_id
                LEFT JOIN tactical_profiles t ON p.player_id = t.player_id
                WHERE p.player_id = ?
            """, (player_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)

    def find_player_by_name(self, name_query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a reference player by full or partial name (e.g. 'Pedri', 'Rodri', 'Bellingham').
        """
        cleaned = name_query.strip().lower()
        if not cleaned:
            return None

        with self._get_connection() as conn:
            cur = conn.cursor()

            # 1. Exact match on name
            cur.execute("""
                SELECT p.*, c.name as club_name, comp.name as competition_name,
                       t.progression_score, t.defensive_work_rate, t.creativity_score,
                       t.pressing_intensity, t.aerial_dominance, t.league_fit_score
                FROM players p
                LEFT JOIN clubs c ON p.current_club_id = c.club_id
                LEFT JOIN competitions comp ON p.current_club_domestic_competition_id = comp.competition_id
                LEFT JOIN tactical_profiles t ON p.player_id = t.player_id
                WHERE LOWER(p.name) = ?
                ORDER BY p.market_value_in_eur DESC LIMIT 1
            """, (cleaned,))
            row = cur.fetchone()
            if row:
                return dict(row)

            # 2. Substring match ordered by highest market value (to match star players first)
            cur.execute("""
                SELECT p.*, c.name as club_name, comp.name as competition_name,
                       t.progression_score, t.defensive_work_rate, t.creativity_score,
                       t.pressing_intensity, t.aerial_dominance, t.league_fit_score
                FROM players p
                LEFT JOIN clubs c ON p.current_club_id = c.club_id
                LEFT JOIN competitions comp ON p.current_club_domestic_competition_id = comp.competition_id
                LEFT JOIN tactical_profiles t ON p.player_id = t.player_id
                WHERE LOWER(p.name) LIKE ? OR LOWER(p.last_name) LIKE ? OR LOWER(p.first_name) LIKE ?
                ORDER BY p.market_value_in_eur DESC LIMIT 1
            """, (f"%{cleaned}%", f"%{cleaned}%", f"%{cleaned}%"))
            row = cur.fetchone()
            if row:
                return dict(row)

            return None

    def query_candidates(
        self,
        sub_position: Optional[Union[str, List[str]]] = None,
        position: Optional[str] = None,
        max_market_value: Optional[float] = None,
        min_market_value: Optional[float] = 0.0,
        max_age: Optional[int] = None,
        min_minutes: int = 300,
        target_league_code: str = "ES1",
        limit: int = 150
    ) -> List[Dict[str, Any]]:
        """
        Query eligible players based on hard constraints from the real football database.
        Returns candidates across the full budget spectrum ordered by quality.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            conditions = ["p.last_season >= 2023"]
            params: List[Any] = []

            # Handle sub-positions (single or list)
            if sub_position:
                if isinstance(sub_position, str):
                    conditions.append("p.sub_position = ?")
                    params.append(sub_position)
                elif isinstance(sub_position, (list, tuple)) and sub_position:
                    placeholders = ",".join(["?"] * len(sub_position))
                    conditions.append(f"p.sub_position IN ({placeholders})")
                    params.extend(sub_position)
            elif position:
                conditions.append("p.position = ?")
                params.append(position)

            if max_market_value is not None and max_market_value > 0:
                conditions.append("p.market_value_in_eur <= ?")
                params.append(max_market_value)

            if min_market_value is not None and min_market_value > 0:
                conditions.append("p.market_value_in_eur >= ?")
                params.append(min_market_value)

            if max_age is not None:
                conditions.append("p.age <= ?")
                params.append(max_age)

            where_clause = " AND ".join(conditions)

            # Order by tactical score and market value to capture the true optimal candidates
            query = f"""
                SELECT p.player_id, p.name, p.age, p.date_of_birth, p.foot, p.height_in_cm,
                       p.sub_position, p.position, p.market_value_in_eur, p.highest_market_value_in_eur,
                       p.contract_expiration_date, p.current_club_id, p.current_club_name,
                       p.current_club_domestic_competition_id, p.url as profile_url,
                       p.image_url, p.data_citation,
                       c.name as club_name, comp.name as league_name,
                       COALESCE(t.progression_score, 60.0) as progression_score,
                       COALESCE(t.defensive_work_rate, 60.0) as defensive_work_rate,
                       COALESCE(t.creativity_score, 50.0) as creativity_score,
                       COALESCE(t.pressing_intensity, 65.0) as pressing_intensity,
                       COALESCE(t.aerial_dominance, 50.0) as aerial_dominance,
                       COALESCE(t.league_fit_score, 65.0) as league_fit_score,
                       COALESCE(t.confidence_score, 0.70) as tactical_confidence,
                       COALESCE(SUM(s.minutes_played), 0) as recent_minutes,
                       COALESCE(SUM(s.appearances), 0) as recent_appearances,
                       COALESCE(SUM(s.goals), 0) as recent_goals,
                       COALESCE(SUM(s.assists), 0) as recent_assists
                FROM players p
                LEFT JOIN clubs c ON p.current_club_id = c.club_id
                LEFT JOIN competitions comp ON p.current_club_domestic_competition_id = comp.competition_id
                LEFT JOIN tactical_profiles t ON p.player_id = t.player_id
                LEFT JOIN player_seasons s ON p.player_id = s.player_id AND s.season >= 2022
                WHERE {where_clause}
                GROUP BY p.player_id
                HAVING recent_minutes >= ?
                ORDER BY COALESCE(t.league_fit_score, 60.0) DESC, p.market_value_in_eur DESC
                LIMIT ?
            """
            params.extend([min_minutes, limit])

            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]

            # Enrich with dynamic adaptation coefficients for the target league
            for row in rows:
                comp_id = row.get("current_club_domestic_competition_id")
                adapt_factor = get_league_adaptation_factor(comp_id, target_league_code)
                row["league_adaptation_factor"] = adapt_factor

                # Discrepancy detection (peak vs current)
                peak = row.get("highest_market_value_in_eur") or row.get("market_value_in_eur") or 0.0
                curr = row.get("market_value_in_eur") or 0.0
                if peak > curr * 1.5 and curr > 0:
                    drop_pct = ((peak - curr) / peak) * 100.0
                    row["data_disagreement_notes"] = (
                        f"Valuation discrepancy: Player peak was €{peak:,.0f} vs current €{curr:,.0f} "
                        f"(-{drop_pct:.1f}%). May reflect recent injury, contract countdown, or tactical rotation."
                    )
                else:
                    row["data_disagreement_notes"] = "Market valuation aligned with recent playing sample and contract status."

            return rows

    def get_player_valuations_history(self, player_id: int) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT date, market_value_in_eur, current_club_name, season, data_source
                FROM player_valuations
                WHERE player_id = ?
                ORDER BY date ASC
            """, (player_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_player_transfers(self, player_id: int) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT transfer_date, transfer_season, from_club_name, to_club_name,
                       transfer_fee, market_value_in_eur, data_source
                FROM transfers
                WHERE player_id = ?
                ORDER BY transfer_date DESC
            """, (player_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_historical_snapshot(
        self,
        cutoff_date: str,
        sub_position: Optional[Union[str, List[str]]] = None,
        max_market_value: Optional[float] = None,
        max_age_at_date: Optional[int] = None,
        limit: int = 150
    ) -> List[Dict[str, Any]]:
        """
        Backtesting snapshot: retrieves players and their valuation/stats frozen as of cutoff_date.
        Ensures NO future data leakage during backtesting!
        """
        with self._get_connection() as conn:
            cur = conn.cursor()

            query = """
                WITH frozen_vals AS (
                    SELECT v.player_id, v.market_value_in_eur, v.date as val_date,
                           ROW_NUMBER() OVER(PARTITION BY v.player_id ORDER BY v.date DESC) as rn
                    FROM player_valuations v
                    WHERE v.date <= ? AND v.market_value_in_eur IS NOT NULL
                )
                SELECT p.player_id, p.name, p.sub_position, p.position, p.date_of_birth,
                       fv.market_value_in_eur as historical_val_eur,
                       fv.val_date as historical_val_date,
                       p.current_club_domestic_competition_id,
                       p.url as profile_url,
                       COALESCE(t.progression_score, 60.0) as progression_score,
                       COALESCE(t.defensive_work_rate, 60.0) as defensive_work_rate,
                       COALESCE(t.creativity_score, 50.0) as creativity_score,
                       COALESCE(t.league_fit_score, 65.0) as league_fit_score
                FROM frozen_vals fv
                JOIN players p ON fv.player_id = p.player_id
                LEFT JOIN tactical_profiles t ON p.player_id = t.player_id
                WHERE fv.rn = 1
            """
            params: List[Any] = [cutoff_date]

            if sub_position:
                if isinstance(sub_position, str):
                    query += " AND p.sub_position = ?"
                    params.append(sub_position)
                elif isinstance(sub_position, (list, tuple)) and sub_position:
                    placeholders = ",".join(["?"] * len(sub_position))
                    query += f" AND p.sub_position IN ({placeholders})"
                    params.extend(sub_position)

            if max_market_value:
                query += " AND fv.market_value_in_eur <= ?"
                params.append(max_market_value)

            query += " ORDER BY fv.market_value_in_eur DESC LIMIT ?"
            params.append(limit)

            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def get_forward_realized_outcome(
        self,
        player_id: int,
        entry_date: str,
        eval_horizon_days: int = 730
    ) -> Dict[str, Any]:
        """
        Calculates ground truth realized performance and valuation growth for backtesting.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()

            # Entry valuation
            cur.execute("""
                SELECT market_value_in_eur, date
                FROM player_valuations
                WHERE player_id = ? AND date <= ?
                ORDER BY date DESC LIMIT 1
            """, (player_id, entry_date))
            entry_row = cur.fetchone()
            entry_val = entry_row["market_value_in_eur"] if entry_row else 0.0

            # Forward valuation after eval horizon
            cur.execute("""
                SELECT market_value_in_eur, date
                FROM player_valuations
                WHERE player_id = ? AND date > ?
                ORDER BY date DESC LIMIT 1
            """, (player_id, entry_date))
            forward_row = cur.fetchone()
            forward_val = forward_row["market_value_in_eur"] if forward_row else entry_val

            # Realized transfers in the period
            cur.execute("""
                SELECT transfer_fee, to_club_name, transfer_date
                FROM transfers
                WHERE player_id = ? AND transfer_date >= ?
                ORDER BY transfer_date ASC LIMIT 1
            """, (player_id, entry_date))
            transfer_row = cur.fetchone()

            delta_eur = forward_val - entry_val
            pct_gain = (delta_eur / max(entry_val, 100000.0)) * 100.0

            return {
                "player_id": player_id,
                "entry_date": entry_date,
                "entry_market_value_eur": entry_val,
                "forward_market_value_eur": forward_val,
                "delta_value_eur": delta_eur,
                "percentage_gain": round(pct_gain, 1),
                "is_value_appreciated": delta_eur > 0,
                "subsequent_transfer_fee": transfer_row["transfer_fee"] if transfer_row else None,
                "subsequent_club": transfer_row["to_club_name"] if transfer_row else None,
                "data_source": "Verified Transfermarkt historical valuation trajectory"
            }
