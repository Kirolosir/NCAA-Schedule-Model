"""Team-season NPI aggregation for 2024 Division III men's soccer."""

from dataclasses import dataclass
from math import fsum, isfinite
from typing import Literal, Sequence

from .game_value import calculate_game_value


SeasonResult = Literal["win", "loss", "tie"]
ComponentKind = Literal["win", "loss"]

MINIMUM_RETAINED_WINS = 10.0


@dataclass(frozen=True)
class SeasonGame:
    """One countable Division III game in a team's season."""

    opponent: str
    opponent_npi: float
    result: SeasonResult


@dataclass(frozen=True)
class OutcomeComponent:
    """A win or loss portion of a game and the amount retained in NPI."""

    opponent: str
    kind: ComponentKind
    original_weight: float
    retained_weight: float
    unit_value: float

    @property
    def retained_rating(self) -> float:
        return self.retained_weight * self.unit_value


@dataclass(frozen=True)
class SeasonNPIBreakdown:
    """An auditable season calculation after component inclusion decisions."""

    npi: float
    total_rating: float
    total_weight: float
    retained_win_weight: float
    retained_loss_weight: float
    components: tuple[OutcomeComponent, ...]
    used_winless_rule: bool


@dataclass(frozen=True)
class _CandidateComponent:
    opponent: str
    kind: ComponentKind
    weight: float
    unit_value: float


def calculate_season_npi(
    games: Sequence[SeasonGame],
    *,
    minimum_retained_wins: float = MINIMUM_RETAINED_WINS,
) -> SeasonNPIBreakdown:
    """Aggregate game values into one season NPI."""
    if not games:
        raise ValueError("at least one game is required")
    if not isfinite(minimum_retained_wins) or minimum_retained_wins < 0:
        raise ValueError("minimum_retained_wins must be finite and nonnegative")

    win_candidates: list[_CandidateComponent] = []
    loss_candidates: list[_CandidateComponent] = []

    for game in games:
        if not game.opponent.strip():
            raise ValueError("opponent must not be blank")
        if game.result not in ("win", "loss", "tie"):
            raise ValueError("result must be 'win', 'loss', or 'tie'")

        if game.result in ("win", "tie"):
            win_candidates.append(
                _CandidateComponent(
                    opponent=game.opponent,
                    kind="win",
                    weight=1.0 if game.result == "win" else 0.5,
                    unit_value=calculate_game_value(
                        "win", game.opponent_npi
                    ).total,
                )
            )
        if game.result in ("loss", "tie"):
            loss_candidates.append(
                _CandidateComponent(
                    opponent=game.opponent,
                    kind="loss",
                    weight=1.0 if game.result == "loss" else 0.5,
                    unit_value=calculate_game_value(
                        "loss", game.opponent_npi
                    ).total,
                )
            )

    if not win_candidates:
        npi = min(component.unit_value for component in loss_candidates)
        components = tuple(
            OutcomeComponent(
                opponent=component.opponent,
                kind="loss",
                original_weight=component.weight,
                retained_weight=0.0,
                unit_value=component.unit_value,
            )
            for component in loss_candidates
        )
        return SeasonNPIBreakdown(
            npi=npi,
            total_rating=0.0,
            total_weight=0.0,
            retained_win_weight=0.0,
            retained_loss_weight=0.0,
            components=components,
            used_winless_rule=True,
        )

    win_candidates.sort(key=lambda component: component.unit_value, reverse=True)
    loss_candidates.sort(
        key=lambda component: component.unit_value, reverse=True
    )

    retained_weights: dict[int, float] = {
        id(component): component.weight for component in loss_candidates
    }
    total_rating = fsum(
        component.unit_value * component.weight
        for component in loss_candidates
    )
    total_weight = fsum(component.weight for component in loss_candidates)
    current_npi = total_rating / total_weight if total_weight else 0.0
    retained_win_weight = 0.0

    for component in win_candidates:
        full_rating = component.unit_value * component.weight
        candidate_npi = (total_rating + full_rating) / (
            total_weight + component.weight
        )

        if (
            candidate_npi >= current_npi
            or retained_win_weight + component.weight
            <= minimum_retained_wins
        ):
            retained_weight = component.weight
        elif retained_win_weight >= minimum_retained_wins:
            retained_weight = 0.0
        else:
            retained_weight = minimum_retained_wins - retained_win_weight

        retained_weights[id(component)] = retained_weight
        if retained_weight:
            total_rating += component.unit_value * retained_weight
            total_weight += retained_weight
            retained_win_weight += retained_weight
            current_npi = total_rating / total_weight

    for component in loss_candidates:
        retained_weight = retained_weights[id(component)]
        if not retained_weight or total_weight <= retained_weight:
            continue
        candidate_npi = (
            total_rating - component.unit_value * retained_weight
        ) / (total_weight - retained_weight)
        if candidate_npi < current_npi:
            total_rating -= component.unit_value * retained_weight
            total_weight -= retained_weight
            retained_weights[id(component)] = 0.0
            current_npi = total_rating / total_weight

    all_candidates = [*win_candidates, *loss_candidates]
    components = tuple(
        OutcomeComponent(
            opponent=component.opponent,
            kind=component.kind,
            original_weight=component.weight,
            retained_weight=retained_weights[id(component)],
            unit_value=component.unit_value,
        )
        for component in all_candidates
    )
    retained_loss_weight = fsum(
        component.retained_weight
        for component in components
        if component.kind == "loss"
    )

    return SeasonNPIBreakdown(
        npi=current_npi,
        total_rating=total_rating,
        total_weight=total_weight,
        retained_win_weight=retained_win_weight,
        retained_loss_weight=retained_loss_weight,
        components=components,
        used_winless_rule=False,
    )
