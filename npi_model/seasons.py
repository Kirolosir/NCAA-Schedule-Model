"""Season-specific division graphs and cross-season team comparisons."""

from functools import lru_cache
import json
from pathlib import Path

from .division_npi import DivisionGame

DATA = Path(__file__).resolve().parents[1] / "tests/data"
DEFAULT_SEASON = "2025"
SEASONS = {"2025": "ncaa_2025_11_09_division.json", "2024": "ncaa_2024_10_27_division.json",
           "2023": "ncaa_2023_historical_division.json", "2022": "ncaa_2022_historical_division.json"}
PLANNING_WEIGHTS = (0.5, 0.3, 0.2)


def season_path(season):
    if not isinstance(season, str) or season not in SEASONS:
        raise ValueError("Choose a supported season: " + ", ".join(SEASONS))
    return DATA / SEASONS[season]


@lru_cache(maxsize=4)
def load_season(season=DEFAULT_SEASON):
    data = json.loads(season_path(season).read_text())
    if season == "2024":
        data["source"].update(season="2024", rating_kind="official_npi", snapshot="October 27 snapshot",
                             validation={"records_matched": 407, "published_npi_available": True})
    ratings = {row[0]: row[1] for row in data["teams"]}
    games = tuple(DivisionGame(a, b, r) for _, _, a, b, r in data["games"])
    return data, ratings, games


def catalog():
    return [{"season": season, **load_season(season)[0]["source"]} for season in SEASONS]


@lru_cache(maxsize=4)
def planning_ratings(season=DEFAULT_SEASON):
    _, current, _ = load_season(season)
    if season not in ("2024", "2025"):
        return current
    years = [str(int(season)-offset) for offset in range(3)]
    history = {year: load_season(year)[1] for year in years}
    result = {}
    for team in current:
        rows = [(history[year][team], weight) for year, weight in zip(years, PLANNING_WEIGHTS)
                if team in history[year]]
        total = sum(weight for _, weight in rows)
        result[team] = sum(value*weight for value, weight in rows)/total
    return result


def team_history(team, *, through=DEFAULT_SEASON):
    rows = []
    for season in SEASONS:
        if season > through:
            continue
        data, ratings, _ = load_season(season)
        record = next((r[2] for r in data["teams"] if r[0] == team), None)
        rows.append({"season": season, "npi": ratings.get(team), "record": record,
                     "cutoff": data["source"]["cutoff"], "rating_kind": data["source"]["rating_kind"]})
    return rows
