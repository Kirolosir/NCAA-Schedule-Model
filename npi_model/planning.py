"""Planning inputs, explicit rating/rank bands, and historical graph loading."""

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path

from .division_npi import DivisionGame
from .schedule_simulator import OutcomeProbabilities


DEFAULT_BANDS = (("sub-40", None, 40), ("40-55", 40, 55),
                 ("55-75", 55, 75), ("75-100", 75, 100), ("100+", 100, None))
CONFERENCE = ("Bates", "Bowdoin", "Colby", "Connecticut Col.", "Hamilton",
              "Middlebury", "Trinity (CT)", "Tufts", "Wesleyan (CT)", "Williams")
DEFAULT_POOL = ("Suffolk", "WPI", "Babson", "Manhattanville", "Emerson",
                "Springfield", "Western New Eng.")
DEFAULT_GRAPH = Path(__file__).resolve().parents[1]/"tests/data/ncaa_2024_10_27_division.json"


@dataclass(frozen=True)
class Candidate:
    team: str
    recent_npi: float
    probabilities: OutcomeProbabilities | None = None


@dataclass(frozen=True)
class FixedGame:
    team: str
    category: str = "conference"
    result: str | None = None
    probabilities: OutcomeProbabilities | None = None


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
    # Ordinal positions derived from the displayed ratings; alphabetical tie
    # break is explicit, not a claim to reconstruct hidden NCAA tiebreaks.
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


def default_config():
    return {
        "target_team": "Amherst", "mode": "teams", "band_scale": "rating",
        "fixed_games": [{"team": team, "category": "conference"} for team in CONFERENCE],
        "candidates": [{"team": team} for team in DEFAULT_POOL],
        "bands": [{"label": label, "lower": low, "upper": high}
                  for label, low, high in DEFAULT_BANDS],
        "representatives_per_band": 2, "open_slots": 5, "required": [],
        "excluded": [], "samples": 24, "validation_samples": 64,
        "insight_samples": 8, "top_n": 3, "seed": 20241027,
        "max_combinations": 500, "probability_slope_scale": 0.5,
        "convergence_tolerance": 1e-8,
    }


def probability_override(data):
    if data is None:
        return None
    p = OutcomeProbabilities(**data)
    from .schedule_simulator import enumerate_independent_outcomes
    enumerate_independent_outcomes([p])  # shared strict probability validation
    return p


def parse_plan(config, ratings):
    target = config["target_team"]
    if target not in ratings:
        raise ValueError(f"unknown target: {target}")
    if config.get("band_scale", "rating") not in ("rating", "rank"):
        raise ValueError("band_scale must be 'rating' or 'rank'")
    strength = config.get("target_recent_npi", ratings[target])
    if not isfinite(strength) or not 0 <= strength <= 100:
        raise ValueError("target_recent_npi must be finite and in 0–100")
    fixed = tuple(FixedGame(row["team"], row.get("category", "conference"),
                            row.get("result"), probability_override(row.get("probabilities")))
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
        recent = float(row.get("recent_npi", ratings[team]))
        if not isfinite(recent) or not 0 <= recent <= 100:
            raise ValueError("recent_npi must be finite and in the supported 0–100 domain")
        candidates.append(Candidate(team, recent, probability_override(row.get("probabilities"))))
    if len({c.team for c in candidates}) != len(candidates):
        raise ValueError("duplicate candidates")
    return target, fixed, tuple(sorted(candidates, key=lambda c: c.team)), band_rows
