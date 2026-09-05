"""NCAA Division III men's soccer NPI modeling tools."""

from .division_npi import (
    DivisionGame,
    DivisionNPIResult,
    NPIConvergenceError,
    calculate_adjusted_win_percentages,
    calculate_division_pass,
    iterate_division_npi,
    opponent_win_percentage_seed,
)
from .game_value import GameValueBreakdown, calculate_game_value
from .season_npi import (
    OutcomeComponent,
    SeasonGame,
    SeasonNPIBreakdown,
    calculate_season_npi,
)
from .schedule_simulator import (
    NamedScheduleScenario,
    OutcomeProbabilities,
    ScenarioProjection,
    ScheduleProjection,
    ScheduledOpponent,
    enumerate_independent_outcomes,
    project_schedule_distribution,
    project_schedule_scenario,
    project_schedule_scenarios,
    replace_team_schedule,
)
from .planning import Candidate, FixedGame, default_config, load_graph
from .outcome_model import OutcomeModel
from .schedule_optimizer import ScheduleEvaluator, rank_schedules, risk_reward

__all__ = [
    "Candidate",
    "FixedGame",
    "DivisionGame",
    "DivisionNPIResult",
    "GameValueBreakdown",
    "NamedScheduleScenario",
    "NPIConvergenceError",
    "OutcomeProbabilities",
    "OutcomeModel",
    "OutcomeComponent",
    "ScenarioProjection",
    "ScheduleProjection",
    "ScheduleEvaluator",
    "ScheduledOpponent",
    "SeasonGame",
    "SeasonNPIBreakdown",
    "calculate_adjusted_win_percentages",
    "calculate_division_pass",
    "calculate_game_value",
    "calculate_season_npi",
    "default_config",
    "enumerate_independent_outcomes",
    "iterate_division_npi",
    "load_graph",
    "opponent_win_percentage_seed",
    "project_schedule_distribution",
    "project_schedule_scenario",
    "project_schedule_scenarios",
    "replace_team_schedule",
    "rank_schedules",
    "risk_reward",
]
