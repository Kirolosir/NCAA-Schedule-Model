"""Simultaneous division-wide NPI iteration.

One rating pass must use only opponent ratings from the previous pass.  That
Jacobi-style update matters: updating teams in place would make the answer
depend on team ordering and would not reproduce the NCAA calculation.

No rating is rounded during a pass or while testing for convergence.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Literal, Mapping, Sequence

from .season_npi import (
    MINIMUM_RETAINED_WINS,
    SeasonGame,
    calculate_season_npi,
)


DivisionResult = Literal["win", "loss", "tie"]


@dataclass(frozen=True)
class DivisionGame:
    """One countable game, expressed from ``team_a``'s perspective."""

    team_a: str
    team_b: str
    result_a: DivisionResult


@dataclass(frozen=True)
class DivisionNPIResult:
    """The stable ratings and convergence diagnostics from an iteration."""

    ratings: dict[str, float]
    iterations: int
    final_max_change: float
    convergence_tolerance: float
    max_change_history: tuple[float, ...]


class NPIConvergenceError(RuntimeError):
    """Raised when ratings do not stabilize before the iteration limit."""


def _opposite_result(result: DivisionResult) -> DivisionResult:
    if result == "win":
        return "loss"
    if result == "loss":
        return "win"
    return "tie"


def _build_schedules(
    games: Sequence[DivisionGame],
    eligible_teams: Iterable[str] | None,
) -> tuple[tuple[str, ...], dict[str, tuple[tuple[str, DivisionResult], ...]]]:
    if eligible_teams is None:
        team_set = {game.team_a for game in games}
        team_set.update(game.team_b for game in games)
    else:
        team_set = set(eligible_teams)

    if not team_set:
        raise ValueError("at least one eligible team is required")
    if any(not team.strip() for team in team_set):
        raise ValueError("team names must not be blank")

    schedules: dict[str, list[tuple[str, DivisionResult]]] = {
        team: [] for team in team_set
    }
    for game in games:
        if not game.team_a.strip() or not game.team_b.strip():
            raise ValueError("team names must not be blank")
        if game.team_a == game.team_b:
            raise ValueError("a team cannot play itself")
        if game.result_a not in ("win", "loss", "tie"):
            raise ValueError("result_a must be 'win', 'loss', or 'tie'")

        # A game is countable only when both teams are NPI-eligible.  The real
        # 2024 export contains two D-III teams with records but no published
        # NPI; games involving either are therefore outside the rating graph.
        if game.team_a not in team_set or game.team_b not in team_set:
            continue

        schedules[game.team_a].append((game.team_b, game.result_a))
        schedules[game.team_b].append(
            (game.team_a, _opposite_result(game.result_a))
        )

    teams_without_games = [team for team, schedule in schedules.items() if not schedule]
    if teams_without_games:
        listed = ", ".join(sorted(teams_without_games)[:5])
        raise ValueError(f"eligible teams without countable games: {listed}")

    teams = tuple(sorted(team_set))
    return teams, {
        team: tuple(schedules[team])
        for team in teams
    }


def calculate_adjusted_win_percentages(
    games: Sequence[DivisionGame],
    *,
    eligible_teams: Iterable[str] | None = None,
) -> dict[str, float]:
    """Return each eligible team's 0-100 adjusted win percentage.

    Men's soccer has 1.0 home/away weights, so a win is one adjusted win and a
    tie is half a win plus half a loss.
    """
    teams, schedules = _build_schedules(games, eligible_teams)
    percentages: dict[str, float] = {}
    for team in teams:
        wins = sum(
            1.0 if result == "win" else 0.5 if result == "tie" else 0.0
            for _, result in schedules[team]
        )
        percentages[team] = 100.0 * wins / len(schedules[team])
    return percentages


def opponent_win_percentage_seed(
    games: Sequence[DivisionGame],
    *,
    eligible_teams: Iterable[str] | None = None,
    strength_of_schedule_weight: float = 0.85,
) -> dict[str, float]:
    """Build the NCAA-style initial seed from opponents' win percentages.

    The initial pass omits the team's own result value and quality-win bonus.
    With equal game weights, the seed is 85% of the mean adjusted win
    percentage of a team's opponents.
    """
    if (
        not isfinite(strength_of_schedule_weight)
        or not 0.0 <= strength_of_schedule_weight <= 1.0
    ):
        raise ValueError("strength_of_schedule_weight must be from 0 to 1")

    teams, schedules = _build_schedules(games, eligible_teams)
    win_percentages = calculate_adjusted_win_percentages(
        games,
        eligible_teams=teams,
    )
    return {
        team: strength_of_schedule_weight
        * sum(win_percentages[opponent] for opponent, _ in schedules[team])
        / len(schedules[team])
        for team in teams
    }


def _validate_ratings(
    teams: tuple[str, ...],
    ratings: Mapping[str, float],
    *,
    label: str,
) -> dict[str, float]:
    team_set = set(teams)
    rating_set = set(ratings)
    missing = team_set - rating_set
    extra = rating_set - team_set
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing {len(missing)} team(s)")
        if extra:
            details.append(f"contains {len(extra)} ineligible team(s)")
        raise ValueError(f"{label} " + " and ".join(details))

    validated: dict[str, float] = {}
    for team in teams:
        value = float(ratings[team])
        if not isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError(
                f"{label} for {team!r} must be finite and from 0 to 100"
            )
        validated[team] = value
    return validated


def _calculate_pass_from_schedules(
    teams: tuple[str, ...],
    schedules: Mapping[str, Sequence[tuple[str, DivisionResult]]],
    previous_ratings: Mapping[str, float],
    minimum_retained_wins: float,
) -> dict[str, float]:
    # Build an entirely new mapping.  No value calculated in this pass can be
    # observed by another team until the next pass.
    return {
        team: calculate_season_npi(
            [
                SeasonGame(
                    opponent=opponent,
                    opponent_npi=previous_ratings[opponent],
                    result=result,
                )
                for opponent, result in schedules[team]
            ],
            minimum_retained_wins=minimum_retained_wins,
        ).npi
        for team in teams
    }


def calculate_division_pass(
    games: Sequence[DivisionGame],
    previous_ratings: Mapping[str, float],
    *,
    eligible_teams: Iterable[str] | None = None,
    minimum_retained_wins: float = MINIMUM_RETAINED_WINS,
) -> dict[str, float]:
    """Calculate exactly one simultaneous rating pass."""
    teams, schedules = _build_schedules(games, eligible_teams)
    previous = _validate_ratings(teams, previous_ratings, label="previous_ratings")
    return _calculate_pass_from_schedules(
        teams,
        schedules,
        previous,
        minimum_retained_wins,
    )


def iterate_division_npi(
    games: Sequence[DivisionGame],
    *,
    eligible_teams: Iterable[str] | None = None,
    initial_ratings: Mapping[str, float] | None = None,
    convergence_tolerance: float = 1e-10,
    max_iterations: int = 10_000,
    minimum_retained_wins: float = MINIMUM_RETAINED_WINS,
) -> DivisionNPIResult:
    """Iterate simultaneous passes until every team changes by at most tolerance.

    When ``initial_ratings`` is omitted, the NCAA-style opponent-win-percentage
    seed is used.  A supplied mapping must cover every eligible team exactly.
    """
    if not isfinite(convergence_tolerance) or convergence_tolerance <= 0.0:
        raise ValueError("convergence_tolerance must be finite and positive")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")

    teams, schedules = _build_schedules(games, eligible_teams)
    if initial_ratings is None:
        current = opponent_win_percentage_seed(
            games,
            eligible_teams=teams,
        )
    else:
        current = _validate_ratings(
            teams,
            initial_ratings,
            label="initial_ratings",
        )

    max_change_history: list[float] = []
    for iteration in range(1, max_iterations + 1):
        next_ratings = _calculate_pass_from_schedules(
            teams,
            schedules,
            current,
            minimum_retained_wins,
        )
        max_change = max(
            abs(next_ratings[team] - current[team]) for team in teams
        )
        max_change_history.append(max_change)
        current = next_ratings

        if max_change <= convergence_tolerance:
            return DivisionNPIResult(
                ratings=current,
                iterations=iteration,
                final_max_change=max_change,
                convergence_tolerance=convergence_tolerance,
                max_change_history=tuple(max_change_history),
            )

    raise NPIConvergenceError(
        "division NPI did not converge after "
        f"{max_iterations} iterations; final maximum change was "
        f"{max_change_history[-1]:.12g}"
    )
