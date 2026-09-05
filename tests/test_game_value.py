import unittest

from npi_model.game_value import calculate_game_value


class TestGameValue(unittest.TestCase):
    def test_loss_to_roughly_66_npi_team(self) -> None:
        value = calculate_game_value("loss", 66.0)
        self.assertAlmostEqual(value.total, 56.1)
        self.assertEqual(value.quality_win_bonus, 0.0)

    def test_win_below_quality_bonus_threshold(self) -> None:
        value = calculate_game_value("win", 51.5)
        self.assertAlmostEqual(value.total, 58.775)
        self.assertEqual(value.quality_win_bonus, 0.0)

    def test_win_above_quality_bonus_threshold(self) -> None:
        value = calculate_game_value("win", 55.0)
        self.assertAlmostEqual(value.result_component, 15.0)
        self.assertAlmostEqual(value.opponent_component, 46.75)
        self.assertAlmostEqual(value.quality_win_bonus, 0.75)
        self.assertAlmostEqual(value.total, 62.5)

    def test_exact_threshold_does_not_receive_bonus(self) -> None:
        value = calculate_game_value("win", 54.0)
        self.assertEqual(value.quality_win_bonus, 0.0)
        self.assertAlmostEqual(value.total, 60.9)

    def test_invalid_result_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_game_value("tie", 60.0)  # type: ignore[arg-type]

    def test_invalid_opponent_npi_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_game_value("win", 101.0)


if __name__ == "__main__":
    unittest.main()

