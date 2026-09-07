import json
import unittest
from collections import defaultdict

from npi_model.fast_division import CompiledDivision
from npi_model.seasons import load_season
from npi_model.temporal_model import fit_historical, historical_model, transition_rows


class TestSeasonData(unittest.TestCase):
    def test_2025_matches_published_from_multiple_seeds(self):
        data, published, games = load_season("2025")
        compiled = CompiledDivision(games, published)
        results = [compiled.solve(seed, tolerance=1e-10) for seed in
                   (published, {t: 50.0 for t in published}, {t: 0.0 for t in published})]
        self.assertEqual([r.iterations for r in results], [170, 360, 389])
        for result in results:
            self.assertLess(max(abs(result.ratings[t]-published[t]) for t in published), .001)
            self.assertLess(max(abs(result.ratings[t]-results[0].ratings[t]) for t in published), 1e-8)
        self.assertEqual(data["source"]["validation"]["records_matched"], 402)

    def test_historical_records_reaggregate_from_distinct_games(self):
        for season, team_count in (("2022", 408), ("2023", 411)):
            with self.subTest(season=season):
                data, ratings, games = load_season(season)
                counts = defaultdict(lambda: [0, 0, 0])
                for _, _, a, b, outcome in data["all_games"]:
                    counts[a][("win", "loss", "tie").index(outcome)] += 1
                    counts[b][("loss", "win", "tie").index(outcome)] += 1
                self.assertEqual({t: counts[t] for t in data["all_results_records"]}, data["all_results_records"])
                self.assertEqual(len(ratings), team_count)
                self.assertEqual(len(games), data["source"]["eligible_npi_games"])
                self.assertFalse(data["source"]["validation"]["published_npi_available"])
        discrepancy = load_season("2022")[0]["source"]["validation"]["record_discrepancies"]
        self.assertEqual(discrepancy[0]["team"], "Earlham")
        self.assertEqual(discrepancy[0]["schedule_record"], [3, 12, 1])


class TestTemporalModel(unittest.TestCase):
    def test_prior_season_rows_and_holdout_are_out_of_time(self):
        rows, source = transition_rows("2025")
        self.assertEqual(len(rows), 3528)
        self.assertEqual(source["predictor_season"], "2024")
        self.assertLess(source["predictor_cutoff"], "2025-01-01")

    def test_saved_fit_reproduces_and_history_earns_its_place(self):
        saved_model, saved_diagnostics = historical_model("2025")
        rebuilt = fit_historical("2025")
        self.assertEqual(saved_model.slope, rebuilt["model"]["slope"])
        self.assertEqual(saved_model.tie_log_weight, rebuilt["model"]["tie_log_weight"])
        self.assertEqual(saved_diagnostics, rebuilt["diagnostics"])
        self.assertLess(saved_diagnostics["holdout_log_loss"], saved_diagnostics["constant_holdout_log_loss"])
        self.assertLess(saved_diagnostics["holdout_log_loss"], saved_diagnostics["recent_only_holdout_log_loss"])


if __name__ == "__main__":
    unittest.main()
