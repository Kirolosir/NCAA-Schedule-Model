"""Scenario and probability-based schedule projection.

A proposed target-team schedule is inserted into a background division graph,
then the entire division is reconverged.  Opponent NPIs are never held fixed.
No intermediate rounding is performed.
"""

from dataclasses import dataclass
from itertools import product
from math import fsum, isclose, isfinite, prod
from typing import Iterable, Literal, Mapping, Sequence

from .division_npi import (
    DivisionGame,
    DivisionNPIResult,
    DivisionResult,
    iterate_division_npi,
)
from .season_npi import MINIMUM_RETAINED_WINS


ScheduleCategory = Literal["conference", "nonconference"]


@dataclass(frozen=True)
class ScheduledOpponent:
    """One opponent slot in the target team's proposed schedule."""

    opponent: str
    category: ScheduleCategory
    label: str = ""


@dataclass(frozen=True)
class OutcomeProbabilities:
    """Independent win/tie/loss probabilities for one proposed game."""

    win: float
    tie: float
    loss: float

    def as_items(self) -> tuple[tuple[DivisionResult, float], ...]:
        return (
            ("win", self.win),
            ("tie", self.tie),
            ("loss", self.loss),
        )


@dataclass(frozen=True)
class NamedScheduleScenario:
    """A complete target-team outcome scenario."""

    name: str
    outcomes: tuple[DivisionResult, ...]
    probability: float | None = None


@dataclass(frozen=True)
class ScenarioProjection:
    """One scenario after reconverging the full division."""

    name: str
    outcomes: tuple[DivisionResult, ...]
    probability: float | None
    target_npi: float
    convergence: DivisionNPIResult


@dataclass(frozen=True)
class ScheduleProjection:
    """A collection of scenarios and its resulting target-NPI range."""

    target_team: str
    scheduled_opponents: tuple[ScheduledOpponent, ...]
    scenarios: tuple[ScenarioProjection, ...]
    minimum_npi: float
    maximum_npi: float
    minimum_scenario: str
    maximum_scenario: str
    expected_npi: float | None


def _validate_schedule(
    target_team: str,
    scheduled_opponents: Sequence[ScheduledOpponent],
    eligible_teams: Iterable[str],
) -> tuple[ScheduledOpponent, ...]:
    if not target_team.strip():
        raise ValueError("target_team must not be blank")

    eligible = set(eligible_teams)
    if target_team not in eligible:
        raise ValueError("target_team must be NPI-eligible")
    if not scheduled_opponents:
        raise ValueError("at least one scheduled opponent is required")

    validated = tuple(scheduled_opponents)
    for game in validated:
        if not game.opponent.strip():
            raise ValueError("opponent must not be blank")
        if game.opponent == target_team:
            raise ValueError("the target team cannot schedule itself")
        if game.opponent not in eligible:
            raise ValueError(
                f"opponent {game.opponent!r} is not in the eligible NPI graph"
            )
        if game.category not in ("conference", "nonconference"):
            raise ValueError(
                "category must be 'conference' or 'nonconference'"
            )
    return validated


def _validate_outcomes(
    outcomes: Sequence[DivisionResult],
    expected_count: int,
) -> tuple[DivisionResult, ...]:
    validated = tuple(outcomes)
    if len(validated) != expected_count:
        raise ValueError(
            f"scenario has {len(validated)} outcomes; expected {expected_count}"
        )
    if any(result not in ("win", "loss", "tie") for result in validated):
        raise ValueError("outcomes must be 'win', 'loss', or 'tie'")
    return validated


def _validate_probability(value: float, *, label: str) -> float:
    numeric = float(value)
    if not isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{label} must be finite and from 0 to 1")
    return numeric


def replace_team_schedule(
    background_games: Sequence[DivisionGame],
    *,
    target_team: str,
    scheduled_opponents: Sequence[ScheduledOpponent],
    outcomes: Sequence[DivisionResult],
    eligible_teams: Iterable[str],
) -> list[DivisionGame]:
    """Replace all background games involving the target team.

    Removing the old game removes it from both participants because a
    ``DivisionGame`` is a single shared edge.  Each proposed game is then added
    once from the target team's perspective; the division iterator supplies
    the reciprocal result to the opponent.
    """
    eligible = set(eligible_teams)
    schedule = _validate_schedule(
        target_team,
        scheduled_opponents,
        eligible,
    )
    scenario_outcomes = _validate_outcomes(outcomes, len(schedule))

    retained = [
        game
        for game in background_games
        if game.team_a != target_team and game.team_b != target_team
    ]
    retained.extend(
        DivisionGame(target_team, game.opponent, result)
        for game, result in zip(schedule, scenario_outcomes, strict=True)
    )
    return retained


def project_schedule_scenario(
    background_games: Sequence[DivisionGame],
    *,
    target_team: str,
    scheduled_opponents: Sequence[ScheduledOpponent],
    scenario: NamedScheduleScenario,
    eligible_teams: Iterable[str],
    initial_ratings: Mapping[str, float] | None = None,
    convergence_tolerance: float = 1e-10,
    max_iterations: int = 10_000,
    minimum_retained_wins: float = MINIMUM_RETAINED_WINS,
) -> ScenarioProjection:
    """Project one explicit scenario through full-division convergence."""
    eligible = set(eligible_teams)
    schedule = _validate_schedule(
        target_team,
        scheduled_opponents,
        eligible,
    )
    outcomes = _validate_outcomes(scenario.outcomes, len(schedule))
    if scenario.probability is not None:
        probability = _validate_probability(
            scenario.probability,
            label="scenario probability",
        )
    else:
        probability = None

    projected_games = replace_team_schedule(
        background_games,
        target_team=target_team,
        scheduled_opponents=schedule,
        outcomes=outcomes,
        eligible_teams=eligible,
    )
    convergence = iterate_division_npi(
        projected_games,
        eligible_teams=eligible,
        initial_ratings=initial_ratings,
        convergence_tolerance=convergence_tolerance,
        max_iterations=max_iterations,
        minimum_retained_wins=minimum_retained_wins,
    )
    return ScenarioProjection(
        name=scenario.name,
        outcomes=outcomes,
        probability=probability,
        target_npi=convergence.ratings[target_team],
        convergence=convergence,
    )


def project_schedule_scenarios(
    background_games: Sequence[DivisionGame],
    *,
    target_team: str,
    scheduled_opponents: Sequence[ScheduledOpponent],
    scenarios: Sequence[NamedScheduleScenario],
    eligible_teams: Iterable[str],
    initial_ratings: Mapping[str, float] | None = None,
    convergence_tolerance: float = 1e-10,
    max_iterations: int = 10_000,
    minimum_retained_wins: float = MINIMUM_RETAINED_WINS,
) -> ScheduleProjection:
    """Project named scenarios and summarize their target-NPI range.

    ``expected_npi`` is populated only when every scenario has a probability
    and those probabilities sum to one.  Otherwise the scenarios are treated
    as an unweighted sensitivity set.
    """
    if not scenarios:
        raise ValueError("at least one scenario is required")

    eligible = set(eligible_teams)
    schedule = _validate_schedule(
        target_team,
        scheduled_opponents,
        eligible,
    )
    projections = tuple(
        project_schedule_scenario(
            background_games,
            target_team=target_team,
            scheduled_opponents=schedule,
            scenario=scenario,
            eligible_teams=eligible,
            initial_ratings=initial_ratings,
            convergence_tolerance=convergence_tolerance,
            max_iterations=max_iterations,
            minimum_retained_wins=minimum_retained_wins,
        )
        for scenario in scenarios
    )

    minimum = min(projections, key=lambda projection: projection.target_npi)
    maximum = max(projections, key=lambda projection: projection.target_npi)

    probabilities = [projection.probability for projection in projections]
    if all(probability is not None for probability in probabilities):
        total_probability = fsum(
            probability for probability in probabilities if probability is not None
        )
        if not isclose(total_probability, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("scenario probabilities must sum to 1")
        expected_npi = fsum(
            projection.target_npi * projection.probability
            for projection in projections
            if projection.probability is not None
        )
    else:
        if any(probability is not None for probability in probabilities):
            raise ValueError(
                "either every scenario or no scenario must have a probability"
            )
        expected_npi = None

    return ScheduleProjection(
        target_team=target_team,
        scheduled_opponents=schedule,
        scenarios=projections,
        minimum_npi=minimum.target_npi,
        maximum_npi=maximum.target_npi,
        minimum_scenario=minimum.name,
        maximum_scenario=maximum.name,
        expected_npi=expected_npi,
    )


def enumerate_independent_outcomes(
    probabilities: Sequence[OutcomeProbabilities],
    *,
    max_scenarios: int = 10_000,
) -> tuple[NamedScheduleScenario, ...]:
    """Expand independent game probabilities into exact joint scenarios.

    Zero-probability outcomes are omitted.  The explicit limit prevents an
    accidental ``3 ** number_of_games`` explosion; larger schedules should use
    a deliberately selected scenario set or a later sampling layer.
    """
    if not probabilities:
        raise ValueError("at least one probability triple is required")
    if max_scenarios < 1:
        raise ValueError("max_scenarios must be at least 1")

    outcome_options: list[tuple[tuple[DivisionResult, float], ...]] = []
    for game_index, probability in enumerate(probabilities, start=1):
        items = tuple(
            (result, _validate_probability(value, label=f"game {game_index} {result}"))
            for result, value in probability.as_items()
        )
        if not isclose(
            fsum(value for _, value in items),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"game {game_index} outcome probabilities must sum to 1"
            )
        positive = tuple((result, value) for result, value in items if value > 0.0)
        outcome_options.append(positive)

    scenario_count = prod(len(options) for options in outcome_options)
    if scenario_count > max_scenarios:
        raise ValueError(
            f"exact distribution requires {scenario_count} scenarios, above "
            f"the max_scenarios limit of {max_scenarios}"
        )

    scenarios = []
    for combination in product(*outcome_options):
        outcomes = tuple(result for result, _ in combination)
        joint_probability = prod(value for _, value in combination)
        scenarios.append(
            NamedScheduleScenario(
                name="-".join(result[0].upper() for result in outcomes),
                outcomes=outcomes,
                probability=joint_probability,
            )
        )
    return tuple(scenarios)


def project_schedule_distribution(
    background_games: Sequence[DivisionGame],
    *,
    target_team: str,
    scheduled_opponents: Sequence[ScheduledOpponent],
    outcome_probabilities: Sequence[OutcomeProbabilities],
    eligible_teams: Iterable[str],
    initial_ratings: Mapping[str, float] | None = None,
    max_scenarios: int = 10_000,
    convergence_tolerance: float = 1e-10,
    max_iterations: int = 10_000,
    minimum_retained_wins: float = MINIMUM_RETAINED_WINS,
) -> ScheduleProjection:
    """Calculate an exact probability-weighted schedule projection."""
    if len(scheduled_opponents) != len(outcome_probabilities):
        raise ValueError(
            "scheduled_opponents and outcome_probabilities must have equal length"
        )
    scenarios = enumerate_independent_outcomes(
        outcome_probabilities,
        max_scenarios=max_scenarios,
    )
    return project_schedule_scenarios(
        background_games,
        target_team=target_team,
        scheduled_opponents=scheduled_opponents,
        scenarios=scenarios,
        eligible_teams=eligible_teams,
        initial_ratings=initial_ratings,
        convergence_tolerance=convergence_tolerance,
        max_iterations=max_iterations,
        minimum_retained_wins=minimum_retained_wins,
    )
