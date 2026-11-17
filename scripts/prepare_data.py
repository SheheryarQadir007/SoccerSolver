#!/usr/bin/env python3
"""
SoccerSolver - Data Ingestion and Database Preparation
Verified Open Football Datasets: Transfermarkt Open Datasets (dcaribou/transfermarkt-datasets, ODbL License)
"""

import csv
import gzip
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "soccersolver" / "data"
DB_PATH = DATA_DIR / "soccersolver.db"
TMP_DIR = Path("/tmp")

DATA_FILES = {
    "competitions": TMP_DIR / "competitions.csv.gz",
    "clubs": TMP_DIR / "clubs.csv.gz",
    "players": TMP_DIR / "players.csv.gz",
    "player_valuations": TMP_DIR / "player_valuations.csv.gz",
    "transfers": TMP_DIR / "transfers.csv.gz",
    "appearances": TMP_DIR / "appearances.csv.gz",
}

SOURCE_CITATION = (
    "Transfermarkt Open Dataset (dcaribou/transfermarkt-datasets, Open Database License ODbL). "
    "Official player profiles and historical records."
)


def ensure_data_files():
    """Ensure gzip files exist in /tmp."""
    import urllib.request
    base_url = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"
    for name, path in DATA_FILES.items():
        if not path.exists():
            print(f"Downloading {name}.csv.gz...")
            url = f"{base_url}/{name}.csv.gz"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(path, "wb") as f:
                f.write(resp.read())
            print(f"Downloaded {name}.csv.gz ({path.stat().st_size:,} bytes)")


def compute_age(dob_str):
    if not dob_str:
        return None
    try:
        dob = datetime.strptime(dob_str[:10], "%Y-%m-%d")
        today = datetime.now()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


def init_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    PRAGMA foreign_keys = OFF;
    PRAGMA journal_mode = WAL;

    CREATE TABLE competitions (
        competition_id TEXT PRIMARY KEY,
        competition_code TEXT,
        name TEXT,
        sub_type TEXT,
        type TEXT,
        country_id INTEGER,
        country_name TEXT,
        domestic_league_code TEXT,
        confederation TEXT,
        url TEXT,
        data_source TEXT
    );

    CREATE TABLE clubs (
        club_id INTEGER PRIMARY KEY,
        club_code TEXT,
        name TEXT,
        domestic_competition_id TEXT,
        squad_size INTEGER,
        average_age REAL,
        foreigners_number INTEGER,
        foreigners_percentage REAL,
        national_team_players INTEGER,
        stadium_name TEXT,
        stadium_seats INTEGER,
        net_transfer_record TEXT,
        coach_name TEXT,
        last_season INTEGER,
        url TEXT,
        data_source TEXT,
        FOREIGN KEY (domestic_competition_id) REFERENCES competitions(competition_id)
    );

    CREATE TABLE players (
        player_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        name TEXT,
        last_season INTEGER,
        current_club_id INTEGER,
        current_club_name TEXT,
        country_of_birth TEXT,
        city_of_birth TEXT,
        country_of_citizenship TEXT,
        date_of_birth TEXT,
        age INTEGER,
        sub_position TEXT,
        position TEXT,
        foot TEXT,
        height_in_cm INTEGER,
        market_value_in_eur REAL,
        highest_market_value_in_eur REAL,
        contract_expiration_date TEXT,
        agent_name TEXT,
        image_url TEXT,
        url TEXT,
        current_club_domestic_competition_id TEXT,
        data_source TEXT,
        data_citation TEXT,
        FOREIGN KEY (current_club_id) REFERENCES clubs(club_id)
    );

    CREATE TABLE player_valuations (
        valuation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER,
        date TEXT,
        market_value_in_eur REAL,
        current_club_name TEXT,
        current_club_id INTEGER,
        player_club_domestic_competition_id TEXT,
        season TEXT,
        data_source TEXT,
        FOREIGN KEY (player_id) REFERENCES players(player_id)
    );

    CREATE TABLE player_seasons (
        player_id INTEGER,
        season INTEGER,
        competition_id TEXT,
        appearances INTEGER,
        minutes_played INTEGER,
        goals INTEGER,
        assists INTEGER,
        yellow_cards INTEGER,
        red_cards INTEGER,
        goals_per_90 REAL,
        assists_per_90 REAL,
        data_source TEXT,
        PRIMARY KEY (player_id, season, competition_id),
        FOREIGN KEY (player_id) REFERENCES players(player_id)
    );

    CREATE TABLE transfers (
        transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER,
        transfer_date TEXT,
        transfer_season TEXT,
        from_club_id INTEGER,
        to_club_id INTEGER,
        from_club_name TEXT,
        to_club_name TEXT,
        transfer_fee REAL,
        market_value_in_eur REAL,
        player_name TEXT,
        data_source TEXT,
        FOREIGN KEY (player_id) REFERENCES players(player_id)
    );

    CREATE TABLE tactical_profiles (
        player_id INTEGER PRIMARY KEY,
        progression_score REAL,
        defensive_work_rate REAL,
        creativity_score REAL,
        pressing_intensity REAL,
        aerial_dominance REAL,
        tactical_versatility REAL,
        league_fit_score REAL,
        confidence_score REAL,
        data_source TEXT,
        FOREIGN KEY (player_id) REFERENCES players(player_id)
    );

    CREATE INDEX idx_players_pos ON players(position, sub_position);
    CREATE INDEX idx_players_val ON players(market_value_in_eur);
    CREATE INDEX idx_players_comp ON players(current_club_domestic_competition_id);
    CREATE INDEX idx_players_age ON players(age);
    CREATE INDEX idx_val_player_date ON player_valuations(player_id, date);
    CREATE INDEX idx_seasons_player ON player_seasons(player_id, season);
    CREATE INDEX idx_transfers_player ON transfers(player_id);
    """)

    conn.commit()
    return conn


def load_competitions(conn):
    print("Loading competitions...")
    cur = conn.cursor()
    with gzip.open(DATA_FILES["competitions"], "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append((
                r.get("competition_id"),
                r.get("competition_code"),
                r.get("name"),
                r.get("sub_type"),
                r.get("type"),
                int(r["country_id"]) if r.get("country_id") and r["country_id"] != "-1" else None,
                r.get("country_name"),
                r.get("domestic_league_code"),
                r.get("confederation"),
                r.get("url"),
                SOURCE_CITATION
            ))
        cur.executemany("""
            INSERT INTO competitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} competitions.")


def load_clubs(conn):
    print("Loading clubs...")
    cur = conn.cursor()
    with gzip.open(DATA_FILES["clubs"], "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            def to_int(v):
                return int(v) if v and v != "-1" and v.isdigit() else None
            def to_float(v):
                try: return float(v) if v else None
                except ValueError: return None

            rows.append((
                int(r["club_id"]),
                r.get("club_code"),
                r.get("name"),
                r.get("domestic_competition_id"),
                to_int(r.get("squad_size")),
                to_float(r.get("average_age")),
                to_int(r.get("foreigners_number")),
                to_float(r.get("foreigners_percentage")),
                to_int(r.get("national_team_players")),
                r.get("stadium_name"),
                to_int(r.get("stadium_seats")),
                r.get("net_transfer_record"),
                r.get("coach_name"),
                to_int(r.get("last_season")),
                r.get("url"),
                SOURCE_CITATION
            ))
        cur.executemany("""
            INSERT INTO clubs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} clubs.")


def load_players(conn):
    print("Loading players...")
    cur = conn.cursor()
    active_player_ids = set()

    with gzip.open(DATA_FILES["players"], "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            pid = int(r["player_id"])
            last_season = int(r["last_season"]) if r.get("last_season") and r["last_season"].isdigit() else 0
            
            # Keep players active from 2020 onward (for past season backtesting & current windows)
            if last_season < 2020:
                continue

            active_player_ids.add(pid)
            dob_str = r.get("date_of_birth")
            age = compute_age(dob_str)

            def to_int(v):
                try: return int(v) if v else None
                except ValueError: return None
            def to_float(v):
                try: return float(v) if v else None
                except ValueError: return None

            mkt_val = to_float(r.get("market_value_in_eur"))
            high_val = to_float(r.get("highest_market_value_in_eur"))
            club_id = to_int(r.get("current_club_id"))

            rows.append((
                pid,
                r.get("first_name"),
                r.get("last_name"),
                r.get("name"),
                last_season,
                club_id,
                r.get("current_club_name"),
                r.get("country_of_birth"),
                r.get("city_of_birth"),
                r.get("country_of_citizenship"),
                dob_str,
                age,
                r.get("sub_position"),
                r.get("position"),
                r.get("foot"),
                to_int(r.get("height_in_cm")),
                mkt_val,
                high_val,
                r.get("contract_expiration_date"),
                r.get("agent_name"),
                r.get("image_url"),
                r.get("url"),
                r.get("current_club_domestic_competition_id"),
                "Transfermarkt (dcaribou/transfermarkt-datasets, ODbL)",
                f"Source: Transfermarkt profile {r.get('url')} - Retrieved from verified open dataset."
            ))

        cur.executemany("""
            INSERT INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} active players (seasons 2020-2026).")
    return active_player_ids


def load_valuations(conn, active_player_ids):
    print("Loading valuations for active players...")
    cur = conn.cursor()
    with gzip.open(DATA_FILES["player_valuations"], "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            pid = int(r["player_id"])
            if pid not in active_player_ids:
                continue

            def to_float(v):
                try: return float(v) if v else None
                except ValueError: return None
            def to_int(v):
                try: return int(v) if v else None
                except ValueError: return None

            date_str = r.get("date")
            season = None
            if date_str:
                try:
                    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    # Football season typically July to June
                    if dt.month >= 7:
                        season = f"{dt.year}/{dt.year + 1}"
                    else:
                        season = f"{dt.year - 1}/{dt.year}"
                except Exception:
                    pass

            rows.append((
                pid,
                date_str,
                to_float(r.get("market_value_in_eur")),
                r.get("current_club_name"),
                to_int(r.get("current_club_id")),
                r.get("player_club_domestic_competition_id"),
                season,
                "Transfermarkt Valuation History (ODbL)"
            ))

        cur.executemany("""
            INSERT INTO player_valuations (player_id, date, market_value_in_eur, current_club_name, current_club_id, player_club_domestic_competition_id, season, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} historical valuations.")


def load_appearances(conn, active_player_ids):
    print("Aggregating appearances into player_seasons...")
    # Aggregate in memory to avoid huge table size
    # Key: (player_id, season_year, competition_id)
    seasons_agg = {}

    with gzip.open(DATA_FILES["appearances"], "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            pid = int(r["player_id"])
            if pid not in active_player_ids:
                continue

            date_str = r.get("date")
            if not date_str:
                continue
            try:
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                season_year = dt.year if dt.month >= 7 else dt.year - 1
            except Exception:
                continue

            comp_id = r.get("competition_id", "UNKNOWN")
            key = (pid, season_year, comp_id)

            if key not in seasons_agg:
                seasons_agg[key] = {
                    "appearances": 0,
                    "minutes_played": 0,
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                }

            acc = seasons_agg[key]
            acc["appearances"] += 1
            acc["minutes_played"] += int(r.get("minutes_played") or 0)
            acc["goals"] += int(r.get("goals") or 0)
            acc["assists"] += int(r.get("assists") or 0)
            acc["yellow_cards"] += int(r.get("yellow_cards") or 0)
            acc["red_cards"] += int(r.get("red_cards") or 0)

    print(f"Writing {len(seasons_agg)} player season aggregates...")
    cur = conn.cursor()
    rows = []
    for (pid, season_year, comp_id), stats in seasons_agg.items():
        mins = stats["minutes_played"]
        nineties = max(mins / 90.0, 0.1)
        g90 = round(stats["goals"] / nineties, 3)
        a90 = round(stats["assists"] / nineties, 3)
        rows.append((
            pid,
            season_year,
            comp_id,
            stats["appearances"],
            mins,
            stats["goals"],
            stats["assists"],
            stats["yellow_cards"],
            stats["red_cards"],
            g90,
            a90,
            "Transfermarkt Match Appearances (ODbL)"
        ))

    cur.executemany("""
        INSERT OR REPLACE INTO player_seasons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print("Done inserting player seasons.")


def load_transfers(conn, active_player_ids):
    print("Loading transfers...")
    cur = conn.cursor()
    with gzip.open(DATA_FILES["transfers"], "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            pid = int(r["player_id"])
            if pid not in active_player_ids:
                continue

            def to_float(v):
                try: return float(v) if v else None
                except ValueError: return None
            def to_int(v):
                try: return int(v) if v else None
                except ValueError: return None

            rows.append((
                pid,
                r.get("transfer_date"),
                r.get("transfer_season"),
                to_int(r.get("from_club_id")),
                to_int(r.get("to_club_id")),
                r.get("from_club_name"),
                r.get("to_club_name"),
                to_float(r.get("transfer_fee")),
                to_float(r.get("market_value_in_eur")),
                r.get("player_name"),
                "Transfermarkt Real Transfer Records (ODbL)"
            ))

        cur.executemany("""
            INSERT INTO transfers (player_id, transfer_date, transfer_season, from_club_id, to_club_id, from_club_name, to_club_name, transfer_fee, market_value_in_eur, player_name, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
    conn.commit()
    print(f"Inserted {len(rows)} real transfer records.")


def generate_tactical_profiles(conn):
    print("Generating derived tactical & style metrics...")
    cur = conn.cursor()

    # Query all active players with aggregated season data
    cur.execute("""
        SELECT p.player_id, p.sub_position, p.position, p.height_in_cm, p.age,
               COALESCE(SUM(s.minutes_played), 0) as total_mins,
               COALESCE(SUM(s.goals), 0) as total_goals,
               COALESCE(SUM(s.assists), 0) as total_assists,
               COALESCE(SUM(s.yellow_cards), 0) as total_yellows,
               p.current_club_domestic_competition_id
        FROM players p
        LEFT JOIN player_seasons s ON p.player_id = s.player_id AND s.season >= 2022
        GROUP BY p.player_id
    """)
    players = cur.fetchall()

    profiles = []
    for pid, sub_pos, pos, height, age, mins, goals, assists, yellows, comp_id in players:
        nineties = max(mins / 90.0, 1.0)
        h = height if height else 180
        age_val = age if age else 25

        # Tactical features grounded in position and real stats:
        # 1. Progression: Fullbacks/Midfielders with high minutes and assists
        if sub_pos in ("Left-Back", "Right-Back", "Left Wing-Back", "Right Wing-Back"):
            progression = min(99.0, max(45.0, 60.0 + (assists / nineties) * 60 + (mins / 3000.0) * 15))
            defensive = min(99.0, max(40.0, 65.0 + (yellows / nineties) * 10 + (h > 182) * 5))
            creativity = min(99.0, max(35.0, 50.0 + (assists / nineties) * 70))
            pressing = min(99.0, max(45.0, 70.0 - (age_val - 20) * 1.2))
            aerial = min(99.0, max(30.0, (h - 170) * 2.2))
        elif pos == "Defender":
            progression = min(95.0, max(40.0, 50.0 + (assists / nineties) * 40))
            defensive = min(99.0, max(55.0, 75.0 + (h > 185) * 8))
            creativity = min(90.0, max(30.0, 40.0 + (assists / nineties) * 50))
            pressing = min(95.0, max(40.0, 65.0 - (age_val - 20) * 1.0))
            aerial = min(99.0, max(40.0, (h - 175) * 2.5 + 40))
        elif pos == "Midfield":
            progression = min(99.0, max(50.0, 65.0 + (assists / nineties) * 50 + (goals / nineties) * 30))
            defensive = min(95.0, max(40.0, 60.0 + (yellows / nineties) * 15))
            creativity = min(99.0, max(50.0, 65.0 + (assists / nineties) * 80))
            pressing = min(99.0, max(45.0, 72.0 - (age_val - 20) * 1.1))
            aerial = min(95.0, max(30.0, (h - 175) * 2.0 + 35))
        else: # Attack
            progression = min(99.0, max(45.0, 60.0 + (goals / nineties) * 40 + (assists / nineties) * 40))
            defensive = min(85.0, max(25.0, 40.0 + (yellows / nineties) * 10))
            creativity = min(99.0, max(45.0, 60.0 + (assists / nineties) * 80))
            pressing = min(95.0, max(40.0, 68.0 - (age_val - 20) * 1.3))
            aerial = min(99.0, max(35.0, (h - 175) * 2.2 + 35))

        versatility = min(95.0, max(50.0, 60.0 + (mins > 1500) * 15 + (age_val < 26) * 10))
        
        # League style fit for La Liga: technical progression + discipline
        league_fit = round((progression * 0.4 + defensive * 0.3 + versatility * 0.3), 1)
        
        # Confidence score based on sample size of minutes played
        sample_confidence = min(0.98, max(0.40, mins / 2500.0 * 0.90 + 0.10))

        profiles.append((
            pid,
            round(progression, 1),
            round(defensive, 1),
            round(creativity, 1),
            round(pressing, 1),
            round(aerial, 1),
            round(versatility, 1),
            league_fit,
            round(sample_confidence, 2),
            "Derived from Transfermarkt match appearances & physical profiles"
        ))

    cur.executemany("""
        INSERT OR REPLACE INTO tactical_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, profiles)
    conn.commit()
    print(f"Generated tactical profiles for {len(profiles)} players.")


def main():
    print("=" * 60)
    print("SoccerSolver - Real Football Database Builder")
    print("Complete Sources, Licenses & Citations.")
    print("=" * 60)
    ensure_data_files()
    conn = init_database()
    load_competitions(conn)
    load_clubs(conn)
    active_player_ids = load_players(conn)
    load_valuations(conn, active_player_ids)
    load_appearances(conn, active_player_ids)
    load_transfers(conn, active_player_ids)
    generate_tactical_profiles(conn)
    conn.close()
    size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    print(f"\nSUCCESS: Database built at {DB_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
