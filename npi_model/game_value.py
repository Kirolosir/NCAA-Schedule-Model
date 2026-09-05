"""Single-game NPI value calculation.

This module deliberately contains only the per-game formula. Team-level rules,
including iterative opponent NPI convergence and any minimum-win adjustment,
belong in later modules so that each modeling assumption remains visible.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Literal


Result = Literal["win", "loss"]

WIN_VALUE = 100.0
LOSS_VALUE = 0.0
RESULT_WEIGHT = 0.15
OPPONENT_NPI_WEIGHT = 0.85
QUALITY_WIN_THRESHOLD = 54.0
QUALITY_WIN_BONUS_RATE = 0.75


@dataclass(frozen=True)
class GameValueBreakdown:
    """The auditable pieces that make up one game's NPI value."""

    result: Result
    opponent_npi: float
    result_component: float
    opponent_component: float
    quality_win_bonus: float
    total: float


def calculate_game_value(result: Result, opponent_npi: float) -> GameValueBreakdown:
    """Calculate one game's NPI value from its result and opponent NPI.

    Formula:
        0.15 * result value + 0.85 * opponent NPI + quality-win bonus

    A win is worth 100 result points and a loss is worth 0. A win over an
    opponent above 54.0 receives a bonus of 0.75 times the amount above 54.0.
    No rounding is performed inside the calculation.

    Ties are intentionally not accepted until their official treatment is
    confirmed from source data or NCAA documentation.
    """
    if result not in ("win", "loss"):
        raise ValueError("result must be 'win' or 'loss'")
    if not isfinite(opponent_npi) or not 0.0 <= opponent_npi <= 100.0:
        raise ValueError("opponent_npi must be a finite number from 0 to 100")

    result_value = WIN_VALUE if result == "win" else LOSS_VALUE
    result_component = RESULT_WEIGHT * result_value
    opponent_component = OPPONENT_NPI_WEIGHT * opponent_npi
    quality_win_bonus = (
        (opponent_npi - QUALITY_WIN_THRESHOLD) * QUALITY_WIN_BONUS_RATE
        if result == "win" and opponent_npi > QUALITY_WIN_THRESHOLD
        else 0.0
    )
    total = result_component + opponent_component + quality_win_bonus

    return GameValueBreakdown(
        result=result,
        opponent_npi=opponent_npi,
        result_component=result_component,
        opponent_component=opponent_component,
        quality_win_bonus=quality_win_bonus,
        total=total,
    )

