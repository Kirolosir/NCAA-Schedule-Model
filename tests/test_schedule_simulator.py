import json
import unittest
from math import fsum
from pathlib import Path

from npi_model.division_npi import DivisionGame
from npi_model.schedule_simulator import (
    NamedScheduleScenario,
    OutcomeProbabilities,
    ScheduledOpponent,
    enumerate_independent_outcomes,
    project_schedule_distribution,
    project_schedule_scenario,
    replace_team_schedule,
)


FIXTURE_PATH = (
    Path(__file__).parent / "data" / "ncaa_2024_10_27_division.json"
)


def opposite(result):
    if result == "win":
        return "loss"
    if result == "loss":
        return "win"
    return "tie"


class TestRealDivisionScheduleSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text())
        cls.published = {
            team: npi for team, npi, _, _ in fixture["teams"]
        }
        cls.eligible = set(cls.published)
        cls.games = [
            DivisionGame(away, home, result)
            for _, _, away, home, result in fixture["games"]
        ]

        cls.target = "Amherst"
        target_schedule = []
        target_outcomes = []
        for game in cls.games:
            if game.team_a == cls.target:
                target_schedule.append(
                    ScheduledOpponent(game.team_b, "nonconference")
                )
                target_outcomes.append(game.result_a)
            elif game.team_b == cls.target:
                target_schedule.append(
                    ScheduledOpponent(game.team_a, "nonconference")
                )
                target_outcomes.append(opposite(game.result_a))
        cls.target_schedule = tuple(target_schedule)
        cls.target_outcomes = tuple(target_outcomes)

    def test_reinserting_real_amherst_schedule_restores_verified_graph(self) -> None:
        rebuilt = replace_team_schedule(
            self.games,
            target_team=self.target,
            scheduled_opponents=self.target_schedule,
            outcomes=self.target_outcomes,
            eligible_teams=self.eligible,
        )
        self.assertEqual(len(rebuilt), len(self.games))

        projection = project_schedule_scenario(
            self.games,
            target_team=self.target,
            scheduled_opponents=self.target_schedule,
            scenario=NamedScheduleScenario(
                "historical outcomes",
                self.target_outcomes,
            ),
            eligible_teams=self.eligible,
            initial_ratings=self.published,
        )

        self.assertEqual(projection.convergence.iterations, 83)
        self.assertLess(
            abs(projection.target_npi - self.published[self.target]),
            0.001,
        )

    def test_real_graph_probability_projection_is_probability_weighted(self) -> None:
        probabilities = []
        for index, historical_result in enumerate(self.target_outcomes):
            if index == 0:
                probabilities.append(OutcomeProbabilities(0.6, 0.0, 0.4))
            else:
                probabilities.append(
                    OutcomeProbabilities(
                        1.0 if historical_result == "win" else 0.0,
                        1.0 if historical_result == "tie" else 0.0,
                        1.0 if historical_result == "loss" else 0.0,
                    )
                )

        projection = project_schedule_distribution(
            self.games,
            target_team=self.target,
            scheduled_opponents=self.target_schedule,
            outcome_probabilities=probabilities,
            eligible_teams=self.eligible,
            initial_ratings=self.published,
        )

        self.assertEqual(len(projection.scenarios), 2)
        expected = fsum(
            scenario.target_npi * scenario.probability
            for scenario in projection.scenarios
            if scenario.probability is not None
        )
        self.assertEqual(projection.expected_npi, expected)
        self.assertLessEqual(projection.minimum_npi, expected)
        self.assertGreaterEqual(projection.maximum_npi, expected)


class TestOutcomeEnumeration(unittest.TestCase):
    def test_exact_enumeration_refuses_combinatorial_explosion(self) -> None:
        uncertain_games = [OutcomeProbabilities(0.4, 0.2, 0.4)] * 9
        with self.assertRaisesRegex(ValueError, "19683 scenarios"):
            enumerate_independent_outcomes(uncertain_games)

    def test_probabilities_must_sum_to_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "must sum to 1"):
            enumerate_independent_outcomes(
                [OutcomeProbabilities(0.6, 0.2, 0.3)]
            )


if __name__ == "__main__":
    unittest.main()
