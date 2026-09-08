"""Planning inputs, explicit rating/rank bands, and historical graph loading."""

from dataclasses import dataclass
from itertools import combinations
import json
from math import fsum, isfinite
from pathlib import Path

from .division_npi import DivisionGame
from .schedule_simulator import OutcomeProbabilities
from .seasons import DEFAULT_SEASON, planning_ratings, season_path


DEFAULT_BANDS = (("sub-40", None, 40), ("40-55", 40, 55),
                 ("55-75", 55, 75), ("75-100", 75, 100), ("100+", 100, None))
CONFERENCE = ("Bates", "Bowdoin", "Colby", "Connecticut Col.", "Hamilton",
              "Middlebury", "Trinity (CT)", "Tufts", "Wesleyan (CT)", "Williams")
DEFAULT_POOL = ("Suffolk", "WPI", "Babson", "Manhattanville", "Emerson",
                "Springfield", "Western New Eng.")
DEFAULT_GRAPH = season_path(DEFAULT_SEASON)


@dataclass(frozen=True)
class Candidate:
    team: str
    recent_npi: float
    probabilities: OutcomeProbabilities | None = None
    matchup: str = "model"
    venue: str = "either"
    available_dates: tuple[str, ...] = ()
    travel_miles: float = 0.0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class FixedGame:
    team: str
    category: str = "conference"
    result: str | None = None
    probabilities: OutcomeProbabilities | None = None
    decision: str | None = None


def load_graph(path=DEFAULT_GRAPH):
    data = json.loads(Path(path).read_text())
    ratings = {row[0]: row[1] for row in data["teams"]}
    games = [DivisionGame(a, b, r) for _, _, a, b, r in data["games"]]
    return data, ratings, games


def band_members(ratings, lower, upper, *, scale="rating", excluded=()):
    if scale not in ("rating", "rank"):
        raise ValueError("band_scale must be 'rating' or 'rank'")
    if any(x is not None and (not isfinite(x) or x < 0) for x in (lower, upper)):
        raise ValueError("band bounds must be finite and nonnegative")
    if lower is not None and upper is not None and lower >= upper:
        raise ValueError("lower band bound must be below upper")
    ordered = sorted(ratings, key=lambda team: (-ratings[team], team))
    values = ratings if scale == "rating" else {t: i+1 for i, t in enumerate(ordered)}
    return sorted((t for t in ratings if t not in excluded
                   and (lower is None or values[t] >= lower)
                   and (upper is None or values[t] < upper)),
                  key=lambda t: (values[t], t))


def representatives(members, count=2):
    if not isinstance(count, int) or count < 1:
        raise ValueError("representatives_per_band must be a positive integer")
    if len(members) <= count:
        return list(members)
    if count == 1:
        return [members[len(members)//2]]
    return [members[round(i*(len(members)-1)/(count-1))] for i in range(count)]


def default_config(season=DEFAULT_SEASON):
    _, ratings, _ = load_graph(season_path(season))
    ordered = sorted(CONFERENCE, key=lambda team: (ratings[team], team))
    results = {team: "win" if i < 4 else "tie" if i < 6 else "loss"
               for i, team in enumerate(ordered)}
    return {
        "season": season,
        "probability_model": "historical" if season in ("2024", "2025") else "retrospective",
        "target_team": "Amherst", "target_npi": 60.0,
        "mode": "teams", "band_scale": "rating",
        "fixed_games": [{"team": team, "category": "conference", "result": results[team]}
                        for team in CONFERENCE],
        "candidates": [{"team": team} for team in DEFAULT_POOL],
        "bands": [{"label": label, "lower": low, "upper": high}
                  for label, low, high in DEFAULT_BANDS],
        "representatives_per_band": 2, "open_slots": 5, "required": [],
        "preferred": [], "excluded": [], "max_total_travel_miles": None,
        "max_total_cost": None, "samples": 24, "validation_samples": 64,
        "insight_samples": 8, "top_n": 3, "seed": 20241027,
        "max_combinations": 500, "probability_slope_scale": 1.0 if season in ("2024", "2025") else 0.5,
        "convergence_tolerance": 1e-8, "analysis_mode": "thorough",
        "include_standalone_insights": True,
    }


def probability_override(data):
    if data is None:
        return None
    p = OutcomeProbabilities(**data)
    from .schedule_simulator import enumerate_independent_outcomes
    enumerate_independent_outcomes([p])  # shared strict probability validation
    return p


def assign_dates(candidates):
    dated = sorted((candidate for candidate in candidates if candidate.available_dates),
                   key=lambda candidate: (len(candidate.available_dates), candidate.team))
    assigned = {}
    used = set()
    def place(index):
        if index == len(dated):
            return True
        candidate = dated[index]
        for day in candidate.available_dates:
            if day in used:
                continue
            assigned[candidate.team] = day
            used.add(day)
            if place(index+1):
                return True
            used.remove(day)
            del assigned[candidate.team]
        return False
    return assigned if place(0) else None


def candidate_schedules(candidates, slots, required=(), preferred=(), *,
                        max_travel_miles=None, max_cost=None):
    by_team = {candidate.team: candidate for candidate in candidates}
    required = set(required)
    preferred = set(preferred)
    optional = sorted(set(by_team)-required)
    schedules = []
    for extra in combinations(optional, slots-len(required)):
        opponents = tuple(sorted(required | set(extra)))
        selected = [by_team[team] for team in opponents]
        dates = assign_dates(selected)
        if dates is None:
            continue
        travel = fsum(candidate.travel_miles for candidate in selected)
        cost = fsum(candidate.estimated_cost for candidate in selected)
        if max_travel_miles is not None and travel > max_travel_miles:
            continue
        if max_cost is not None and cost > max_cost:
            continue
        schedules.append({"opponents": opponents, "logistics": {
            "preferred_count": len(set(opponents) & preferred),
            "total_travel_miles": travel, "total_cost": cost,
            "games": [{"team": candidate.team,
                       "priority": "required" if candidate.team in required else
                                   "preferred" if candidate.team in preferred else "available",
                       "venue": candidate.venue, "date": dates.get(candidate.team),
                       "available_dates": list(candidate.available_dates),
                       "travel_miles": candidate.travel_miles,
                       "estimated_cost": candidate.estimated_cost}
                      for candidate in selected]}})
    return schedules


def parse_plan(config, ratings):
    target = config["target_team"]
    if target not in ratings:
        raise ValueError(f"unknown target: {target}")
    if config.get("band_scale", "rating") not in ("rating", "rank"):
        raise ValueError("band_scale must be 'rating' or 'rank'")
    strengths = planning_ratings(config.get("season", DEFAULT_SEASON))
    strength = config.get("target_recent_npi", strengths[target])
    if not isfinite(strength) or not 0 <= strength <= 100:
        raise ValueError("target_recent_npi must be finite and in 0–100")
    fixed = tuple(FixedGame(row["team"], row.get("category", "conference"),
                            row.get("result"), probability_override(row.get("probabilities")),
                            row.get("decision"))
                  for row in config["fixed_games"])
    if not fixed:
        raise ValueError("fixed_games must include at least one baseline game")
    for game in fixed:
        if game.team not in ratings or game.team == target:
            raise ValueError(f"invalid fixed opponent: {game.team}")
        if game.category not in ("conference", "nonconference"):
            raise ValueError("invalid fixed-game category")
        if game.result not in (None, "win", "tie", "loss"):
            raise ValueError("invalid locked game result")
        if game.result is not None and game.probabilities is not None:
            raise ValueError("locked results cannot also have outcome probabilities")
        if game.decision not in (None, "advanced_on_penalties", "eliminated_on_penalties"):
            raise ValueError("invalid penalty-kick decision")
        if game.decision is not None and game.result != "tie":
            raise ValueError("a penalty-kick decision must be recorded as a tie")
    if len({g.team for g in fixed}) != len(fixed):
        raise ValueError("duplicate fixed opponents are unsupported; use unique opponents")
    if not set(config.get("excluded", [])) <= set(ratings):
        raise ValueError("excluded contains an unknown team")
    excluded = set(config.get("excluded", [])) | {target} | {g.team for g in fixed}
    band_rows = []
    for band in config.get("bands", []):
        members = band_members(ratings, band.get("lower"), band.get("upper"),
                               scale=config.get("band_scale", "rating"), excluded=excluded)
        band_rows.append({**band, "member_count": len(members),
                          "representatives": representatives(members, config.get("representatives_per_band", 2))})
    mode = config.get("mode", "teams")
    if mode == "bands":
        names = sorted({t for band in band_rows for t in band["representatives"]})
        raw = [{"team": t} for t in names]
    elif mode == "teams":
        raw = config["candidates"]
    else:
        raise ValueError("mode must be 'teams' or 'bands'")
    candidates = []
    for row in raw:
        team = row["team"]
        if team not in ratings:
            raise ValueError(f"{team!r} has no division schedule profile; import its games first")
        if team in excluded:
            if team in config.get("excluded", []):
                continue
            raise ValueError(f"candidate {team!r} is the target or a fixed opponent")
        recent = float(row.get("recent_npi", strengths.get(team, ratings[team])))
        if not isfinite(recent) or not 0 <= recent <= 100:
            raise ValueError("recent_npi must be finite and in the supported 0–100 domain")
        probabilities = probability_override(row.get("probabilities"))
        matchup = row.get("matchup", "custom" if probabilities else "model")
        if matchup not in ("model", "favorite", "toss_up", "underdog", "custom"):
            raise ValueError("matchup must be model, favorite, toss_up, underdog, or custom")
        if (matchup == "model") != (probabilities is None):
            raise ValueError("matchup presets and custom outlooks need outcome probabilities")
        venue = row.get("venue", "either")
        if venue not in ("home", "away", "either"):
            raise ValueError("venue must be home, away, or either")
        dates = row.get("available_dates", [])
        if not isinstance(dates, list) or any(not isinstance(day, str) for day in dates):
            raise ValueError("available_dates must be a list of dates")
        travel = float(row.get("travel_miles", 0))
        cost = float(row.get("estimated_cost", 0))
        if not isfinite(travel) or travel < 0 or not isfinite(cost) or cost < 0:
            raise ValueError("travel miles and estimated cost must be nonnegative")
        candidates.append(Candidate(team, recent, probabilities, matchup, venue,
                                    tuple(sorted(set(dates))), travel, cost))
    if len({c.team for c in candidates}) != len(candidates):
        raise ValueError("duplicate candidates")
    return target, fixed, tuple(sorted(candidates, key=lambda c: c.team)), band_rows
