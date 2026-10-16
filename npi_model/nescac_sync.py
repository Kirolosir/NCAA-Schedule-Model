"""Checks Amherst's own public athletics schedule for finished NESCAC games.

This only ever reads one page (Amherst men's soccer, athletics.amherst.edu),
which the site's robots.txt allows. It never touches stats.ncaa.org or
ncaa.com, both of which disallow automated access. Results are cached for a
few hours so a coach clicking "check for results" a few times in a row
doesn't cause a fresh request each time.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import ssl
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

import certifi
from bs4 import BeautifulSoup

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

SCHEDULE_URL = "https://athletics.amherst.edu/sports/mens-soccer/schedule/{year}"
USER_AGENT = "ScheduleLabSync/1.0 (github.com/Kirolosir/NCAA-Schedule-Model)"
REQUEST_TIMEOUT_SECONDS = 8
CACHE_TTL_SECONDS = 3 * 60 * 60

# The ten NESCAC opponents, from the athletics site's full school name to
# the short name the rest of the app already uses for that same team.
OPPONENT_ALIASES = {
    "Bates College": "Bates",
    "Bowdoin College": "Bowdoin",
    "Colby College": "Colby",
    "Connecticut College": "Connecticut Col.",
    "Hamilton College": "Hamilton",
    "Middlebury College": "Middlebury",
    "Trinity College": "Trinity (CT)",
    "Tufts University": "Tufts",
    "Wesleyan University": "Wesleyan (CT)",
    "Williams College": "Williams",
}

RESULT_LETTERS = {"W": "win", "T": "tie", "L": "loss"}

_cache = {}
_status = {}


def _timestamp(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


@dataclass
class SyncedGame:
    team: str
    result: str
    date: str | None
    score: str | None


def _parse(html):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select("li.sidearm-schedule-game"):
        raise ValueError("No recognizable schedule entries found; no results were updated")
    games = []
    for item in soup.select("li.sidearm-schedule-game"):
        letter = next((c for c in item.get("class", []) if c in RESULT_LETTERS), None)
        if letter is None:
            continue
        conference = item.select_one(".sidearm-schedule-game-conference")
        if not conference or conference.get_text(strip=True) != "NESCAC":
            continue
        name_el = item.select_one(".sidearm-schedule-game-opponent-name")
        opponent = OPPONENT_ALIASES.get(name_el.get_text(strip=True)) if name_el else None
        if opponent is None:
            continue
        date_el = item.select_one(".sidearm-schedule-game-opponent-date span")
        score_el = item.select_one("[class*='result']")
        games.append(SyncedGame(team=opponent, result=RESULT_LETTERS[letter],
                                date=date_el.get_text(strip=True) if date_el else None,
                                score=score_el.get_text(strip=True) if score_el else None))
    if len({game.team for game in games}) != len(games):
        raise ValueError("The page includes rematches; review regular-season and playoff results separately")
    return games


def fetch_amherst_nescac_results(year=None, *, force=False):
    year = year or date.today().year
    cached = _cache.get(year)
    if cached and not force and time.time()-cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    url = SCHEDULE_URL.format(year=year)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS, context=_SSL_CONTEXT) as response:
        html = response.read().decode("utf-8", errors="replace")
    games = _parse(html)
    _cache[year] = (time.time(), games)
    return games


def sync_summary(year=None):
    year = year or date.today().year
    checked = time.time()
    cached = _cache.get(year)
    from_cache = bool(cached and checked-cached[0] < CACHE_TTL_SECONDS)
    source = SCHEDULE_URL.format(year=year)
    error = None
    try:
        games = fetch_amherst_nescac_results(year)
    except (URLError, TimeoutError, OSError) as failure:
        error = f"Could not reach Amherst Athletics: {failure}"
        games = cached[1] if cached else []
    except Exception as failure:  # the site's markup can change without notice
        error = f"Could not read the schedule page: {failure}"
        games = cached[1] if cached else []
    successful = _cache.get(year)
    previous = _status.get(year, {})
    fetched_at = (_timestamp(cached[0]) if cached else previous.get("fetched_at")) if error else (
        _timestamp(successful[0]) if successful else None)
    summary = {"results": [asdict(g) for g in games], "source": source, "error": error,
               "year": year, "checked_at": _timestamp(checked),
               "fetched_at": fetched_at,
               "cached": from_cache and not error, "stale": bool(error and cached)}
    _status[year] = summary
    return summary
