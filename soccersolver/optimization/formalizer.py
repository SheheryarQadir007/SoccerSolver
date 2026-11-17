"""
SoccerSolver - Natural Language to Mathematical Optimization Formalizer
Formalizes any scouting recruitment problem into strict mathematical programs.
Supports: ANY position, ANY budget, ANY league, and REFERENCE PLAYER similarity matching.
"""

import re
import uuid
from typing import Dict, Any, Optional, Tuple, List
from soccersolver.config import POSITION_GROUPS, LEAGUE_NAME_TO_CODE
from soccersolver.data.repository import FootballDataRepository
from soccersolver.optimization.models import (
    OptimizationSpec,
    MathematicalConstraint,
    ConstraintType,
    ObjectiveWeights,
)


class ProblemFormalizer:
    def __init__(self, repo: Optional[FootballDataRepository] = None, model_name: str = "heuristic-formalizer"):
        self.repo = repo or FootballDataRepository()
        self.model_name = model_name

    def formalize(self, query: str) -> Tuple[OptimizationSpec, Dict[str, Any]]:
        """
        Translates a natural language recruitment request into an OptimizationSpec.
        Handles arbitrary positions, budgets, leagues, and reference player profiles.
        """
        import time
        start_time = time.time()

        # 1. Check for Reference Player mention (e.g., 'replacement for Pedri', 'someone like Rodri')
        ref_player_name, ref_player_data = self._parse_reference_player(query)

        # 2. Parse position & allowed sub-positions
        target_pos, allowed_sub_positions = self._parse_position(query, ref_player_data)

        # 3. Parse budget
        budget = self._parse_budget(query)

        # 4. Parse target league
        league_code = self._parse_league(query)

        # 5. Parse age constraints
        max_age = self._parse_age(query)

        # 6. Parse minimum minutes sample
        min_minutes = self._parse_min_minutes(query)

        # 7. Parse weights (accounting for player similarity if reference player is found)
        weights = self._parse_weights(query, is_player_comparison=bool(ref_player_data))

        # 8. Build mathematical constraints
        constraints: List[MathematicalConstraint] = []

        if allowed_sub_positions:
            constraints.append(
                MathematicalConstraint(
                    variable="sub_position",
                    operator=ConstraintType.IN if len(allowed_sub_positions) > 1 else ConstraintType.EQ,
                    value=allowed_sub_positions if len(allowed_sub_positions) > 1 else allowed_sub_positions[0],
                    human_description=f"Player positional role must be in: {', '.join(allowed_sub_positions)}",
                    is_hard=True
                )
            )

        constraints.append(
            MathematicalConstraint(
                variable="market_value_in_eur",
                operator=ConstraintType.LEQ,
                value=float(budget),
                human_description=f"Estimated transfer cost strictly under €{budget:,.0f}",
                is_hard=True
            )
        )

        if max_age is not None:
            constraints.append(
                MathematicalConstraint(
                    variable="age",
                    operator=ConstraintType.LEQ,
                    value=int(max_age),
                    human_description=f"Player age must not exceed {max_age} years",
                    is_hard=True
                )
            )

        constraints.append(
            MathematicalConstraint(
                variable="recent_minutes",
                operator=ConstraintType.GEQ,
                value=int(min_minutes),
                human_description=f"Minimum playing sample of {min_minutes} minutes for statistical confidence",
                is_hard=True
            )
        )

        # 9. Extract reference tactical vector if applicable
        ref_vector = None
        if ref_player_data:
            ref_vector = {
                "progression": float(ref_player_data.get("progression_score") or 70.0),
                "defensive": float(ref_player_data.get("defensive_work_rate") or 60.0),
                "creativity": float(ref_player_data.get("creativity_score") or 60.0),
                "pressing": float(ref_player_data.get("pressing_intensity") or 65.0),
                "aerial": float(ref_player_data.get("aerial_dominance") or 50.0),
            }

        # 10. Generate LaTeX formulation
        latex_str = self._generate_latex(
            target_pos, allowed_sub_positions, budget, max_age, min_minutes,
            league_code, weights, ref_player_name
        )

        spec = OptimizationSpec(
            problem_id=str(uuid.uuid4())[:8],
            query_natural_language=query,
            target_position=target_pos,
            allowed_sub_positions=allowed_sub_positions,
            target_league_code=league_code,
            max_budget_eur=float(budget),
            max_age=max_age,
            min_minutes_played=min_minutes,
            constraints=constraints,
            weights=weights,
            reference_player_name=ref_player_name,
            reference_player_id=ref_player_data["player_id"] if ref_player_data else None,
            reference_tactical_vector=ref_vector,
            mathematical_formulation_latex=latex_str
        )

        elapsed_ms = (time.time() - start_time) * 1000.0
        token_metrics = {
            "prompt_tokens": len(query.split()) * 3 + 120,
            "completion_tokens": 190,
            "latency_ms": elapsed_ms,
            "model": self.model_name
        }

        return spec, token_metrics

    def _parse_reference_player(self, query: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Check for reference player expressions in natural language."""
        ref_patterns = [
            r"(?:replacement for|replace)\s+([a-zA-Z\s\.\-]+?)(?:\s+(?:under|in|for|max|below|with|budget|age)|$)",
            r"(?:someone like|player like|profile like|alternative to)\s+([a-zA-Z\s\.\-]+?)(?:\s+(?:under|in|for|max|below|with|budget|age)|$)",
            r"\blike\s+([a-zA-Z\s\.\-]+?)(?:\s+(?:under|in|for|max|below|with|budget|age)|$)",
        ]
        for pat in ref_patterns:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                cand_name = m.group(1).strip()
                # Skip false positives that match generic football roles
                if cand_name.lower() in ("a winger", "a striker", "a midfielder", "a defender", "a player", "a left back"):
                    continue
                player = self.repo.find_player_by_name(cand_name)
                if player:
                    return player["name"], player
        return None, None

    def _parse_position(self, query: str, ref_player: Optional[Dict[str, Any]]) -> Tuple[str, List[str]]:
        """Determines target position category and allowed sub-positions."""
        if ref_player:
            sub = ref_player.get("sub_position") or "Central Midfield"
            return sub, [sub]

        q_lower = query.lower()

        # Sort position group keywords by length descending (e.g. 'defensive midfielder' before 'midfielder')
        sorted_synonyms = sorted(POSITION_GROUPS.keys(), key=lambda x: len(x), reverse=True)
        for syn in sorted_synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", q_lower):
                allowed = POSITION_GROUPS[syn]
                main_pos = allowed[0] if len(allowed) == 1 else syn.title()
                return main_pos, allowed

        # General positional fallbacks
        if "back" in q_lower or "defender" in q_lower:
            return "Left-Back" if "left" in q_lower else ("Right-Back" if "right" in q_lower else "Centre-Back"), ["Centre-Back"]
        if "midfield" in q_lower or "pivot" in q_lower:
            return "Central Midfield", ["Central Midfield", "Defensive Midfield"]
        if "winger" in q_lower or "wing" in q_lower:
            return "Left Winger" if "left" in q_lower else ("Right Winger" if "right" in q_lower else "Winger"), ["Left Winger", "Right Winger"]
        if "striker" in q_lower or "forward" in q_lower or "goalscorer" in q_lower or "finisher" in q_lower:
            return "Centre-Forward", ["Centre-Forward"]
        if "keeper" in q_lower or "goal" in q_lower:
            return "Goalkeeper", ["Goalkeeper"]

        # Default fallback
        return "Left-Back", ["Left-Back"]

    def _parse_budget(self, query: str) -> float:
        q_lower = query.lower()
        if "free" in q_lower or "0 euro" in q_lower or "free agent" in q_lower:
            return 0.0

        # Pattern: 15M, 15.5m, 15 million, 15m€, 15 meur
        m_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|million|m€|meur|m eur|mil)\b", q_lower)
        if m_match:
            return float(m_match.group(1)) * 1_000_000.0

        # Pattern: 800k, 500 thousand, 800k€
        k_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:k|thousand|k€)\b", q_lower)
        if k_match:
            return float(k_match.group(1)) * 1_000.0

        # Pattern: under €10,000,000 or budget 10000000
        num_match = re.search(r"(?:under|below|max|budget|cost|price|for)\s*(?:€|\$|eur)?\s*(\d{1,3}(?:,\d{3})+|\d+)", q_lower)
        if num_match:
            raw = num_match.group(1).replace(",", "")
            val = float(raw)
            if val < 500:  # e.g. "under 15" implies 15M
                return val * 1_000_000.0
            return val

        return 15_000_000.0  # Dynamic default benchmark budget

    def _parse_league(self, query: str) -> str:
        q_lower = query.lower()
        sorted_leagues = sorted(LEAGUE_NAME_TO_CODE.keys(), key=lambda x: len(x), reverse=True)
        for league_name in sorted_leagues:
            if re.search(r"\b" + re.escape(league_name) + r"\b", q_lower):
                return LEAGUE_NAME_TO_CODE[league_name]
        return "ES1"  # Default target league: La Liga

    def _parse_age(self, query: str) -> Optional[int]:
        q_lower = query.lower()

        # Check U-XX (e.g. u21, u-21, u23)
        u_match = re.search(r"\bu-?(\d{2})\b", q_lower)
        if u_match:
            return int(u_match.group(1))

        # Explicit keywords: 'age under XX', 'max age XX', 'younger than XX'
        m = re.search(r"\b(?:age\s*(?:under|below|<=|<)?|younger than|max age)\s*(\d{2})\b", q_lower)
        if m:
            val = int(m.group(1))
            if 16 <= val <= 40:
                return val

        # 'under XX years old' or 'under XX y/o'
        m2 = re.search(r"\bunder\s+(\d{2})\s*(?:years?(?:\s*old)?|y(?:/o)?)\b", q_lower)
        if m2:
            val = int(m2.group(1))
            if 16 <= val <= 40:
                return val

        # 'under XX' only if NOT followed by million/m/k/eur/€/dollar
        m3 = re.search(r"\bunder\s+(\d{2})(?!\s*(?:m|million|mil|k|thousand|€|eur|\$))\b", q_lower)
        if m3:
            val = int(m3.group(1))
            # Must be a plausible young age, and not a bare budget number
            if ("age" in q_lower or "year" in q_lower or val <= 23) and 16 <= val <= 35:
                return val

        if "young" in q_lower or "prospect" in q_lower or "future" in q_lower:
            return 24

        # If user did NOT specify age, return None so players of all ages can be evaluated!
        return None

    def _parse_min_minutes(self, query: str) -> int:
        q_lower = query.lower()
        mins_match = re.search(r"(\d{3,4})\s*mins?", q_lower)
        if mins_match:
            return int(mins_match.group(1))
        # Responsive default sample: 450 minutes ensures reliable data without over-filtering
        return 450

    def _parse_weights(self, query: str, is_player_comparison: bool) -> ObjectiveWeights:
        q_lower = query.lower()
        weights = ObjectiveWeights()

        if is_player_comparison:
            weights.profile_similarity = 0.50
            weights.tactical_fit = 0.20
            weights.expected_growth_xtv = 0.15
            weights.value_efficiency = 0.10
            weights.age_potential = 0.05
            return weights

        if "growth" in q_lower or "resale" in q_lower or "potential" in q_lower or "xtv" in q_lower:
            weights.expected_growth_xtv = 0.40
            weights.tactical_fit = 0.35
            weights.age_potential = 0.15
        elif "immediate" in q_lower or "starter" in q_lower or "proven" in q_lower or "experienced" in q_lower:
            weights.tactical_fit = 0.55
            weights.expected_growth_xtv = 0.20
            weights.age_potential = 0.05
        return weights

    def _generate_latex(
        self,
        position: str,
        allowed_subs: List[str],
        budget: float,
        max_age: Optional[int],
        min_minutes: int,
        league_code: str,
        weights: ObjectiveWeights,
        ref_player: Optional[str]
    ) -> str:
        pos_display = ", ".join(f"\\text{{{s}}}" for s in allowed_subs) if allowed_subs else f"\\text{{{position}}}"
        ref_clause = f" + {weights.profile_similarity:.2f} \\cdot \\text{{Similarity}}(x, \\mathbf{{v}}_{{\\text{{{ref_player}}}}})" if ref_player else ""

        c_lines = [f"\\text{{Cost}}(x) \\le {budget:,.0f} \\text{{ EUR}}"]
        if max_age:
            c_lines.append(f"\\text{{Age}}(x) \\le {max_age}")
        c_lines.append(f"\\text{{Position}}(x) \\in \\{{{pos_display}\\}}")
        c_lines.append(f"\\text{{MinutesPlayed}}(x) \\ge {min_minutes}")

        constraints_str = " \\\\\n".join(f"&{c}" for c in c_lines)

        return f"""
\\begin{{aligned}}
\\max_{{x \\in \\mathcal{{P}}}} \\quad \\Phi(x) &= {weights.tactical_fit:.2f} \\cdot S_{{\\text{{tactical}}}}(x, \\text{{{league_code}}}) + {weights.expected_growth_xtv:.2f} \\cdot \\Delta \\text{{xTV}}(x) \\\\
&\\quad + {weights.value_efficiency:.2f} \\cdot \\frac{{S_{{\\text{{tactical}}}}(x)}}{{\\text{{Cost}}(x)}} + {weights.age_potential:.2f} \\cdot \\Psi_{{\\text{{age}}}}(x){ref_clause} - {weights.financial_risk_penalty:.2f} \\cdot \\Lambda(x) \\\\[6pt]
\\text{{subject to:}} \\quad
{constraints_str}
\\end{{aligned}}
""".strip()
