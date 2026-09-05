import json
import unittest
from collections import defaultdict
from pathlib import Path

from npi_model.division_npi import (
    DivisionGame,
    calculate_division_pass,
    iterate_division_npi,
    opponent_win_percentage_seed,
)
from npi_model.season_npi import SeasonGame, calculate_season_npi


FIXTURE_PATH = (
    Path(__file__).parent / "data" / "ncaa_2024_10_27_division.json"
)


def load_fixture():
    fixture = json.loads(FIXTURE_PATH.read_text())
    teams = {
        team: {
            "published_npi": npi,
            "diii_record": record,
            "adjusted_record": adjusted_record,
        }
        for team, npi, record, adjusted_record in fixture["teams"]
    }
    games = [
        DivisionGame(away, home, away_result)
        for _, _, away, home, away_result in fixture["games"]
    ]
    return fixture, teams, games


class TestDivisionPass(unittest.TestCase):
    def test_one_pass_is_simultaneous(self) -> None:
        games = [
            DivisionGame("A", "B", "win"),
            DivisionGame("B", "C", "win"),
            DivisionGame("C", "A", "win"),
        ]
        previous = {"A": 10.0, "B": 20.0, "C": 30.0}

        actual = calculate_division_pass(
            games,
            previous,
            minimum_retained_wins=0.0,
        )

        # Each value uses only the supplied previous mapping. In particular,
        # B's loss uses A=10, not A's newly calculated 28.75.
        self.assertAlmostEqual(actual["A"], 28.75)
        self.assertAlmostEqual(actual["B"], 24.5)
        self.assertAlmostEqual(actual["C"], 20.25)

    def test_ineligible_team_and_incident_game_are_excluded(self) -> None:
        games = [
            DivisionGame("A", "B", "win"),
            DivisionGame("A", "Unranked", "loss"),
        ]
        actual = calculate_division_pass(
            games,
            {"A": 50.0, "B": 50.0},
            eligible_teams={"A", "B"},
        )

        self.assertEqual(set(actual), {"A", "B"})
        self.assertAlmostEqual(actual["A"], 57.5)
        self.assertAlmostEqual(actual["B"], 42.5)


class TestOfficial2024DivisionRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture, cls.teams, cls.games = load_fixture()
        cls.eligible_teams = set(cls.teams)
        cls.published = {
            team: data["published_npi"] for team, data in cls.teams.items()
        }

        cls.from_published = iterate_division_npi(
            cls.games,
            eligible_teams=cls.eligible_teams,
            initial_ratings=cls.published,
        )
        cls.from_owp = iterate_division_npi(
            cls.games,
            eligible_teams=cls.eligible_teams,
        )
        cls.from_constant_50 = iterate_division_npi(
            cls.games,
            eligible_teams=cls.eligible_teams,
            initial_ratings={team: 50.0 for team in cls.eligible_teams},
        )
        cls.from_zero = iterate_division_npi(
            cls.games,
            eligible_teams=cls.eligible_teams,
            initial_ratings={team: 0.0 for team in cls.eligible_teams},
        )

    def test_fixture_reconciles_source_scope(self) -> None:
        source = self.fixture["source"]
        self.assertEqual(source["all_export_teams"], 409)
        self.assertEqual(source["all_diii_games"], 3160)
        self.assertEqual(source["eligible_npi_teams"], 407)
        self.assertEqual(source["eligible_npi_games"], 3137)
        self.assertEqual(
            source["excluded_unranked_teams"],
            ["Carlow", "Penn St Brandywine"],
        )

    def test_published_values_are_a_fixed_point_within_export_precision(self) -> None:
        one_pass = calculate_division_pass(
            self.games,
            self.published,
            eligible_teams=self.eligible_teams,
        )
        errors = {
            team: abs(one_pass[team] - self.published[team])
            for team in self.eligible_teams
        }

        self.assertEqual(sum(error < 0.001 for error in errors.values()), 407)
        self.assertLess(max(errors.values()), 0.001)

        schedules = defaultdict(list)
        for game in self.games:
            opposite = (
                "loss"
                if game.result_a == "win"
                else "win"
                if game.result_a == "loss"
                else "tie"
            )
            schedules[game.team_a].append((game.team_b, game.result_a))
            schedules[game.team_b].append((game.team_a, opposite))

        for team, data in self.teams.items():
            with self.subTest(team=team):
                breakdown = calculate_season_npi(
                    [
                        SeasonGame(opponent, self.published[opponent], result)
                        for opponent, result in schedules[team]
                    ]
                )
                expected_wins, expected_losses = (
                    float(value) for value in data["adjusted_record"].split("-")
                )
                self.assertEqual(
                    breakdown.retained_win_weight,
                    expected_wins,
                )
                self.assertEqual(
                    breakdown.retained_loss_weight,
                    expected_losses,
                )

    def test_full_division_converges_to_published_values(self) -> None:
        errors = {
            team: abs(
                self.from_published.ratings[team] - self.published[team]
            )
            for team in self.eligible_teams
        }
        worst_team = max(errors, key=errors.get)

        self.assertEqual(self.from_published.iterations, 83)
        self.assertLessEqual(
            self.from_published.final_max_change,
            self.from_published.convergence_tolerance,
        )
        self.assertEqual(sum(error < 0.001 for error in errors.values()), 407)
        self.assertEqual(worst_team, "TCNJ")
        self.assertAlmostEqual(errors[worst_team], 0.0004991008, places=9)

    def test_starting_seed_does_not_change_the_fixed_point(self) -> None:
        expected_iterations = {
            "published": (self.from_published, 83),
            "opponent win percentage": (self.from_owp, 214),
            "constant 50": (self.from_constant_50, 185),
            "zero": (self.from_zero, 225),
        }
        baseline = self.from_published.ratings

        for name, (result, iterations) in expected_iterations.items():
            with self.subTest(seed=name):
                self.assertEqual(result.iterations, iterations)
                self.assertLess(
                    max(
                        abs(result.ratings[team] - baseline[team])
                        for team in self.eligible_teams
                    ),
                    1e-8,
                )

    def test_default_seed_is_noncircular_and_complete(self) -> None:
        seed = opponent_win_percentage_seed(
            self.games,
            eligible_teams=self.eligible_teams,
        )
        self.assertEqual(set(seed), self.eligible_teams)
        self.assertTrue(all(0.0 <= rating <= 85.0 for rating in seed.values()))


if __name__ == "__main__":
    unittest.main()
