import json
import unittest
from pathlib import Path

from npi_model.season_npi import SeasonGame, calculate_season_npi


FIXTURE_PATH = (
    Path(__file__).parent / "data" / "ncaa_2024_10_27_verification.json"
)


class TestSeasonNPIRules(unittest.TestCase):
    def test_tie_is_half_win_and_half_loss(self) -> None:
        result = calculate_season_npi(
            [SeasonGame("Quality opponent", 60.0, "tie")],
            minimum_retained_wins=0.0,
        )

        win_half = next(c for c in result.components if c.kind == "win")
        loss_half = next(c for c in result.components if c.kind == "loss")
        self.assertEqual(win_half.original_weight, 0.5)
        self.assertEqual(loss_half.original_weight, 0.5)
        self.assertAlmostEqual(win_half.unit_value, 70.5)
        self.assertAlmostEqual(loss_half.unit_value, 51.0)

    def test_all_wins_are_kept_below_minimum(self) -> None:
        result = calculate_season_npi(
            [SeasonGame(f"Opponent {i}", 40.0 + i, "win") for i in range(4)]
        )
        self.assertEqual(result.retained_win_weight, 4.0)

    def test_weak_wins_can_be_dropped_after_minimum(self) -> None:
        games = [SeasonGame(f"Strong {i}", 60.0, "win") for i in range(10)]
        games.append(SeasonGame("Weak", 20.0, "win"))
        result = calculate_season_npi(games)

        weak = next(c for c in result.components if c.opponent == "Weak")
        self.assertEqual(result.retained_win_weight, 10.0)
        self.assertEqual(weak.retained_weight, 0.0)

    def test_exclusion_is_value_based_not_chronological(self) -> None:
        weak_first = [SeasonGame("Weak", 20.0, "win")]
        weak_first.extend(SeasonGame(f"Strong {i}", 60.0, "win") for i in range(10))
        weak_last = [*weak_first[1:], weak_first[0]]
        first = calculate_season_npi(weak_first)
        last = calculate_season_npi(weak_last)
        self.assertEqual(first.npi, last.npi)
        self.assertEqual(first.retained_win_weight, 10.0)
        self.assertEqual(next(c for c in first.components if c.opponent == "Weak").retained_weight, 0.0)

    def test_ties_supply_half_wins_toward_the_floor(self) -> None:
        games = [SeasonGame(f"Strong {i}", 60.0, "win") for i in range(9)]
        games.extend([SeasonGame("Tie one", 60.0, "tie"), SeasonGame("Tie two", 60.0, "tie")])
        games.append(SeasonGame("Weak", 20.0, "win"))
        result = calculate_season_npi(games)
        self.assertEqual(result.retained_win_weight, 10.0)
        self.assertEqual(next(c for c in result.components if c.opponent == "Weak").retained_weight, 0.0)

    def test_high_value_loss_that_raises_npi_is_dropped(self) -> None:
        games = [SeasonGame(f"Win {i}", 40.0, "win") for i in range(10)]
        games.extend(
            [
                SeasonGame("Very strong", 90.0, "loss"),
                SeasonGame("Weak", 20.0, "loss"),
            ]
        )
        result = calculate_season_npi(games)

        strong_loss = next(
            c
            for c in result.components
            if c.opponent == "Very strong" and c.kind == "loss"
        )
        self.assertEqual(strong_loss.retained_weight, 0.0)

    def test_winless_team_uses_lowest_opponent_loss_value(self) -> None:
        result = calculate_season_npi(
            [
                SeasonGame("A", 45.0, "loss"),
                SeasonGame("B", 60.0, "loss"),
            ]
        )
        self.assertTrue(result.used_winless_rule)
        self.assertAlmostEqual(result.npi, 0.85 * 45.0)
        self.assertEqual(result.retained_loss_weight, 0.0)


class TestOfficial2024ExportRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text())

    def test_five_teams_reproduce_published_npi_and_adjusted_record(self) -> None:
        """Use schedules plus opponent NPIs from the official NCAA export."""
        self.assertEqual(len(self.fixture["teams"]), 5)

        for team in self.fixture["teams"]:
            with self.subTest(team=team["team"]):
                games = [
                    SeasonGame(opponent, opponent_npi, result)
                    for opponent, opponent_npi, result in team["games"]
                ]
                actual = calculate_season_npi(games)

                self.assertLess(
                    abs(actual.npi - team["published_npi"]),
                    0.001,
                )
                self.assertAlmostEqual(
                    actual.retained_win_weight,
                    team["adjusted_wins"],
                )
                self.assertAlmostEqual(
                    actual.retained_loss_weight,
                    team["adjusted_losses"],
                )


if __name__ == "__main__":
    unittest.main()
