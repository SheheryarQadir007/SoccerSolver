"""
SoccerSolver - Configuration and Constants
Supports any league, any position, any budget, and player-similarity matching.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "soccersolver" / "data"
DB_PATH = DATA_DIR / "soccersolver.db"

# LLM Pricing (USD per 1M tokens) - Gemini 1.5 Flash / 2.0 Flash defaults
TOKEN_PRICING = {
    "gemini-2.0-flash": {
        "prompt_per_1m": 0.10,
        "completion_per_1m": 0.40,
    },
    "gemini-1.5-pro": {
        "prompt_per_1m": 1.25,
        "completion_per_1m": 5.00,
    },
    "gpt-4o-mini": {
        "prompt_per_1m": 0.15,
        "completion_per_1m": 0.60,
    },
    "heuristic-formalizer": {
        "prompt_per_1m": 0.0,
        "completion_per_1m": 0.0,
    }
}

# Empirical Relative Strength / Intensity Index across Leagues
# Used for dynamic transfer transition coefficient calculation
LEAGUE_STRENGTH_INDEX = {
    "GB1": 1.00,  # Premier League (England)
    "ES1": 0.96,  # La Liga (Spain)
    "IT1": 0.94,  # Serie A (Italy)
    "L1":  0.94,  # Bundesliga (Germany)
    "FR1": 0.90,  # Ligue 1 (France)
    "PO1": 0.84,  # Liga Portugal
    "NL1": 0.82,  # Eredivisie (Netherlands)
    "BE1": 0.79,  # Jupiler Pro League (Belgium)
    "BRA1": 0.78, # Campeonato Brasileiro Série A
    "ARG1": 0.75, # Argentina Primera División
    "TR1": 0.76,  # Süper Lig (Turkey)
    "SA1": 0.74,  # Saudi Pro League
    "MLS1": 0.73, # Major League Soccer (USA)
    "DK1": 0.72,  # Superliga (Denmark)
    "C1":  0.72,  # Swiss Super League
    "A1":  0.72,  # Austrian Bundesliga
    "SC1": 0.71,  # Scottish Premiership
    "GR1": 0.70,  # Super League Greece
    "PL1": 0.68,  # Ekstraklasa (Poland)
    "DEFAULT": 0.70
}

# League Name to Competition Code Mapping
LEAGUE_NAME_TO_CODE = {
    "laliga": "ES1",
    "la liga": "ES1",
    "spain": "ES1",
    "spanish": "ES1",
    "primera division": "ES1",

    "premier league": "GB1",
    "premier": "GB1",
    "epl": "GB1",
    "england": "GB1",
    "english": "GB1",

    "serie a": "IT1",
    "italy": "IT1",
    "italian": "IT1",

    "bundesliga": "L1",
    "germany": "L1",
    "german": "L1",

    "ligue 1": "FR1",
    "france": "FR1",
    "french": "FR1",

    "liga portugal": "PO1",
    "primeira liga": "PO1",
    "portugal": "PO1",
    "portuguese": "PO1",

    "eredivisie": "NL1",
    "netherlands": "NL1",
    "holland": "NL1",
    "dutch": "NL1",

    "belgian pro league": "BE1",
    "jupiler pro league": "BE1",
    "belgium": "BE1",

    "saudi pro league": "SA1",
    "saudi": "SA1",

    "mls": "MLS1",
    "major league soccer": "MLS1",
    "usa": "MLS1",

    "brasileiro": "BRA1",
    "brazil": "BRA1",

    "super lig": "TR1",
    "turkey": "TR1",
    "turkish": "TR1",
}


def get_league_adaptation_factor(origin_code: Optional[str], target_code: Optional[str]) -> float:
    """
    Computes dynamic league adaptation transition coefficient.
    Ratio of origin league competitive intensity to target league competitive intensity.
    """
    orig = origin_code or "DEFAULT"
    targ = target_code or "ES1"
    if orig == targ:
        return 1.00

    s_orig = LEAGUE_STRENGTH_INDEX.get(orig, LEAGUE_STRENGTH_INDEX["DEFAULT"])
    s_targ = LEAGUE_STRENGTH_INDEX.get(targ, LEAGUE_STRENGTH_INDEX["DEFAULT"])

    ratio = s_orig / max(s_targ, 0.50)
    # Clamp between 0.72 (steep adaptation step) and 1.08 (step down in difficulty)
    return round(min(1.08, max(0.72, ratio)), 2)


# Broad Positional Categorization and Specific Sub-positions
POSITION_GROUPS = {
    "fullback": ["Left-Back", "Right-Back"],
    "full-back": ["Left-Back", "Right-Back"],
    "wing back": ["Left-Back", "Right-Back"],
    "wing-back": ["Left-Back", "Right-Back"],
    "wb": ["Left-Back", "Right-Back"],

    "winger": ["Left Winger", "Right Winger"],
    "wide forward": ["Left Winger", "Right Winger"],
    "flank": ["Left Winger", "Right Winger"],

    "midfielder": ["Central Midfield", "Defensive Midfield", "Attacking Midfield"],
    "midfield": ["Central Midfield", "Defensive Midfield", "Attacking Midfield"],
    "central player": ["Central Midfield", "Defensive Midfield", "Attacking Midfield"],

    "striker": ["Centre-Forward"],
    "center forward": ["Centre-Forward"],
    "centre forward": ["Centre-Forward"],
    "cf": ["Centre-Forward"],
    "st": ["Centre-Forward"],
    "forward": ["Centre-Forward", "Second Striker"],
    "attacker": ["Centre-Forward", "Left Winger", "Right Winger", "Second Striker"],

    "defender": ["Centre-Back", "Left-Back", "Right-Back"],
    "centre back": ["Centre-Back"],
    "center back": ["Centre-Back"],
    "cb": ["Centre-Back"],

    "left back": ["Left-Back"],
    "left-back": ["Left-Back"],
    "lb": ["Left-Back"],
    "lwb": ["Left-Back"],

    "right back": ["Right-Back"],
    "right-back": ["Right-Back"],
    "rb": ["Right-Back"],
    "rwb": ["Right-Back"],

    "defensive midfielder": ["Defensive Midfield"],
    "defensive midfield": ["Defensive Midfield"],
    "cdm": ["Defensive Midfield"],
    "dm": ["Defensive Midfield"],
    "pivot": ["Defensive Midfield"],
    "holding midfielder": ["Defensive Midfield"],

    "central midfielder": ["Central Midfield"],
    "central midfield": ["Central Midfield"],
    "cm": ["Central Midfield"],
    "box to box": ["Central Midfield"],
    "b2b": ["Central Midfield"],

    "attacking midfielder": ["Attacking Midfield"],
    "attacking midfield": ["Attacking Midfield"],
    "cam": ["Attacking Midfield"],
    "am": ["Attacking Midfield"],
    "number 10": ["Attacking Midfield"],
    "playmaker": ["Attacking Midfield"],

    "left winger": ["Left Winger"],
    "left wing": ["Left Winger"],
    "lw": ["Left Winger"],

    "right winger": ["Right Winger"],
    "right wing": ["Right Winger"],
    "rw": ["Right Winger"],

    "goalkeeper": ["Goalkeeper"],
    "keeper": ["Goalkeeper"],
    "gk": ["Goalkeeper"],
    "shot stopper": ["Goalkeeper"]
}
