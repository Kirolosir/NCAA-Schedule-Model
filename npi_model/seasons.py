"""Season-specific division graphs and cross-season team comparisons."""

from functools import lru_cache
import json
from pathlib import Path

from .division_npi import DivisionGame

DATA = Path(__file__).resolve().parents[1] / "tests/data"
DEFAULT_SEASON = "2025"
SEASONS = {"2025": "ncaa_2025_11_09_division.json", "2024": "ncaa_2024_10_27_division.json",
           "2023": "ncaa_2023_historical_division.json", "2022": "ncaa_2022_historical_division.json"}


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
