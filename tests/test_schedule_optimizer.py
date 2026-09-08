"""Real-division regression and planning safeguards; no invented opponent pool."""

from dataclasses import replace
import json
import unittest

from npi_model.division_npi import DivisionGame, NPIConvergenceError, iterate_division_npi
from npi_model.fast_division import CompiledDivision
from npi_model.outcome_model import OutcomeModel
from npi_model.planning import (
    Candidate, FixedGame, assign_dates, band_members, candidate_schedules,
    default_config, load_graph, parse_plan, probability_override, representatives,
)
from npi_model.planning_report import render_report
from npi_model.schedule_optimizer import (
    ScheduleEvaluator, _draw, _uniforms, rank_schedules, risk_reward, summarize,
)
from npi_model.schedule_simulator import OutcomeProbabilities
from npi_model.seasons import load_season, planning_ratings, season_path


class RealDataCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.ratings, cls.games = load_graph(season_path("2024"))


class TestFastDivision(RealDataCase):
    def test_all_407_match_reference_and_export(self):
        fast = CompiledDivision(self.games, self.ratings).solve(self.ratings, tolerance=1e-10)
        reference = iterate_division_npi(self.games, eligible_teams=self.ratings,
                                        initial_ratings=self.ratings)
        self.assertEqual(fast.ratings, reference.ratings)
        self.assertEqual(fast.iterations, 83)
        self.assertEqual(fast.max_change_history, reference.max_change_history)
        self.assertEqual(len(fast.ratings), 407)
        self.assertLess(max(abs(fast.ratings[t]-x) for t, x in self.ratings.items()), .001)

    def test_modified_real_graph_matches_reference_from_multiple_seeds(self):
        games = list(self.games)
        index = next(i for i, g in enumerate(games) if "Amherst" in (g.team_a, g.team_b))
        g = games[index]
        games[index] = replace(g, result_a="tie" if g.result_a != "tie" else "loss")
        compiled = CompiledDivision(games, self.ratings)
        reference = iterate_division_npi(games, eligible_teams=self.ratings,
                                        initial_ratings=self.ratings)
        for seed in (self.ratings, {t: 50.0 for t in self.ratings}):
            fast = compiled.solve(seed, tolerance=1e-10)
            self.assertLess(max(abs(fast.ratings[t]-reference.ratings[t]) for t in seed), 1e-8)
        self.assertNotAlmostEqual(reference.ratings["Amherst"], self.ratings["Amherst"], places=3)

    def test_fixed_pass_shortlist_uses_same_iteration_rules(self):
        compiled = CompiledDivision(self.games, self.ratings)
        converged = compiled.solve(self.ratings, tolerance=1e-10, exact=False)
        estimated = compiled.estimate(self.ratings, iterations=converged.iterations)
        self.assertLess(max(abs(estimated[t]-converged.ratings[t]) for t in estimated), 1e-12)

    def test_failure_is_not_reported_as_converged(self):
        with self.assertRaises(NPIConvergenceError):
            CompiledDivision(self.games, self.ratings).solve(self.ratings, max_iterations=1)
        with self.assertRaises(ValueError):
            CompiledDivision(self.games, self.ratings).solve(self.ratings, tolerance=0)

    def test_long_solves_honor_cancellation_checkpoints(self):
        calls = 0
        def stop():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise InterruptedError("stop")
        with self.assertRaises(InterruptedError):
            CompiledDivision(self.games, self.ratings).solve(
                self.ratings, exact=False, checkpoint=stop)
        self.assertEqual(calls, 3)


class TestOutcomeModel(RealDataCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model = OutcomeModel.fit(cls.games, cls.ratings)

    def test_real_fit_and_symmetry(self):
        model = self.model
        self.assertEqual(model.sample_count, 3137)
        self.assertLess(model.fit_log_loss, model.constant_baseline_log_loss)
        self.assertAlmostEqual(model.fit_log_loss, .6968231876793167, places=10)
        a, b = self.ratings["Amherst"], self.ratings["Babson"]
        p, reversed_p = model.predict(a, b), model.predict(b, a)
        self.assertEqual(p.win, reversed_p.loss)
        self.assertEqual(p.tie, reversed_p.tie)
        self.assertAlmostEqual(p.win+p.tie+p.loss, 1.0)
        self.assertAlmostEqual(model.predict(a, a).win, model.predict(a, a).loss)

    def test_explicit_slope_sensitivity_and_domain(self):
        a, b = self.ratings["Amherst"], self.ratings["Manhattanville"]
        softer = replace(self.model, slope=self.model.slope*.5)
        self.assertLess(softer.predict(a, b).win, self.model.predict(a, b).win)
        for invalid in (-1, 101, float("nan")):
            with self.assertRaises(ValueError):
                self.model.predict(a, invalid)


class TestPlanningInputs(RealDataCase):
    def test_planning_strength_uses_three_seasons_without_changing_division_rating(self):
        strengths = planning_ratings("2024")
        _, ratings_2023, _ = load_season("2023")
        _, ratings_2022, _ = load_season("2022")
        expected = .5*self.ratings["Amherst"]+.3*ratings_2023["Amherst"]+.2*ratings_2022["Amherst"]
        self.assertAlmostEqual(strengths["Amherst"], expected)
        self.assertEqual(self.ratings["Amherst"], 60)

    def test_default_real_pool_and_rating_band_scope(self):
        target, fixed, candidates, bands = parse_plan(default_config("2024"), self.ratings)
        self.assertEqual(target, "Amherst")
        self.assertEqual(len(fixed), 10)
        self.assertEqual([sum(g.result == result for g in fixed) for result in ("win", "tie", "loss")], [4, 2, 4])
        by_result = {result: [self.ratings[g.team] for g in fixed if g.result == result]
                     for result in ("win", "tie", "loss")}
        self.assertLessEqual(max(by_result["win"]), min(by_result["tie"]))
        self.assertLessEqual(max(by_result["tie"]), min(by_result["loss"]))
        self.assertEqual(len(candidates), 7)
        self.assertEqual([b["member_count"] for b in bands][-2:], [0, 0])
        self.assertEqual(min(self.ratings.values()), 35.321)
        self.assertEqual(max(self.ratings.values()), 62.061)
        for band in bands:
            self.assertTrue(set(band["representatives"]) <= set(self.ratings))

    def test_rank_band_uses_positions_not_ratings(self):
        members = band_members(self.ratings, 75, 100, scale="rank")
        self.assertEqual(len(members), 25)
        ordered = sorted(self.ratings, key=lambda t: (-self.ratings[t], t))
        self.assertEqual(members, ordered[74:99])
        self.assertFalse(band_members(self.ratings, 75, 100, scale="rating"))

    def test_rating_boundaries_are_half_open_and_reps_are_real(self):
        boundary = self.ratings["Babson"]
        self.assertIn("Babson", band_members(self.ratings, boundary, boundary+1))
        self.assertNotIn("Babson", band_members(self.ratings, boundary-1, boundary))
        names = sorted(self.ratings)
        self.assertEqual(representatives(names, 2), [names[0], names[-1]])
        self.assertEqual(len(representatives(names, 3)), 3)

    def test_banded_mode_generates_named_graph_profiles(self):
        config = default_config("2024")
        config.update(mode="bands", band_scale="rank")
        _, _, candidates, bands = parse_plan(config, self.ratings)
        self.assertEqual({c.team for c in candidates},
                         {t for b in bands for t in b["representatives"]})
        self.assertTrue(all(b["member_count"] for b in bands))

    def test_specific_recent_rating_and_locked_result(self):
        config = default_config("2024")
        config["candidates"][0]["recent_npi"] = 52.123456789
        config["candidates"][0]["probabilities"] = {"win": .4, "tie": .2, "loss": .4}
        config["fixed_games"][0]["result"] = "tie"
        _, fixed, candidates, _ = parse_plan(config, self.ratings)
        c = next(c for c in candidates if c.team == config["candidates"][0]["team"])
        self.assertEqual(c.recent_npi, 52.123456789)
        self.assertEqual(c.probabilities.tie, .2)
        self.assertEqual(fixed[0].result, "tie")

    def test_bad_inputs_fail_instead_of_inventing_profiles(self):
        for patch in ({"candidates": [{"team": "Unknown school"}]},
                      {"candidates": [{"team": "Amherst"}]},
                      {"candidates": [{"team": "Babson", "recent_npi": 101}]},
                      {"target_recent_npi": float("nan")},
                      {"excluded": ["Unknown school"]}):
            config = default_config("2024")
            config.update(patch)
            with self.assertRaises(ValueError):
                parse_plan(config, self.ratings)
        with self.assertRaises(ValueError):
            probability_override({"win": .8, "tie": .3, "loss": .1})

    def test_dates_priorities_travel_and_cost_filter_schedules(self):
        candidates = (
            Candidate("Babson", self.ratings["Babson"], venue="home",
                      available_dates=("2027-09-01",), estimated_cost=250),
            Candidate("Springfield", self.ratings["Springfield"], venue="away",
                      available_dates=("2027-09-01", "2027-09-08"), travel_miles=90,
                      estimated_cost=1200),
            Candidate("Worcester St.", self.ratings["Worcester St."], venue="away",
                      available_dates=("2027-09-01",), travel_miles=150,
                      estimated_cost=1800),
        )
        self.assertEqual(assign_dates(candidates[:2]),
                         {"Babson": "2027-09-01", "Springfield": "2027-09-08"})
        self.assertIsNone(assign_dates((candidates[0], candidates[2])))
        plans = candidate_schedules(candidates, 2, required=["Babson"],
                                    preferred=["Springfield"], max_travel_miles=100,
                                    max_cost=2000)
        self.assertEqual([plan["opponents"] for plan in plans], [("Babson", "Springfield")])
        self.assertEqual(plans[0]["logistics"]["preferred_count"], 1)
        self.assertEqual(plans[0]["logistics"]["total_travel_miles"], 90)
        self.assertEqual(plans[0]["logistics"]["total_cost"], 1450)
        self.assertEqual(plans[0]["logistics"]["games"][1]["date"], "2027-09-08")


class TestScheduleScoring(RealDataCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model = OutcomeModel.fit(cls.games, cls.ratings)
        cls.historical = []
        reverse = {"win": "loss", "loss": "win", "tie": "tie"}
        for g in cls.games:
            if g.team_a == "Amherst":
                cls.historical.append((g.team_b, g.result_a))
            elif g.team_b == "Amherst":
                cls.historical.append((g.team_a, reverse[g.result_a]))

    def evaluator(self):
        return ScheduleEvaluator(self.games, self.ratings, "Amherst",
                                 tuple(FixedGame(t, result=r) for t, r in self.historical if t != "Babson"),
                                 (Candidate("Babson", self.ratings["Babson"]),), self.model)

    def test_historical_replay_and_reciprocal_replacement(self):
        e = self.evaluator()
        self.assertTrue(all("Amherst" not in (g.team_a, g.team_b) for g in e.background))
        historical_result = dict(self.historical)["Babson"]
        actual = e.sample(("Babson",), samples=2, seed=1, forced={"Babson": historical_result})
        self.assertEqual(actual[0], actual[1])
        self.assertLess(abs(actual[0]-self.ratings["Amherst"]), .001)
        self.assertEqual(e.solves, 1)
        e.sample(("Babson",), samples=2, seed=987, forced={"Babson": historical_result})
        self.assertEqual(e.solves, 1)

    def test_conditional_impacts_equal_reference_full_division(self):
        e = self.evaluator()
        row = risk_reward(e, ("Babson",), samples=2, seed=42)[0]
        baseline = e.sample((), samples=2, seed=42)[0]
        for result in ("win", "tie", "loss"):
            graph = e.background + [DivisionGame("Amherst", t, r)
                                     for t, r in self.historical if t != "Babson"]
            graph.append(DivisionGame("Amherst", "Babson", result))
            expected = iterate_division_npi(graph, eligible_teams=self.ratings,
                                           initial_ratings=self.ratings).ratings["Amherst"]
            self.assertAlmostEqual(row[result]["npi"]["mean"], expected, places=6)
            self.assertAlmostEqual(row[result]["impact"]["mean"], expected-baseline, places=6)

    def test_random_streams_and_locked_result_safeguards(self):
        self.assertEqual(_uniforms(4, "Babson", 8)[:4], _uniforms(4, "Babson", 4))
        self.assertNotEqual(_uniforms(4, "Babson", 4), _uniforms(4, "WPI", 4))
        p = OutcomeProbabilities(.4, .2, .4)
        self.assertEqual([_draw(p, x) for x in (.1, .5, .9)], ["win", "tie", "loss"])
        e = self.evaluator()
        with self.assertRaises(ValueError):
            e.sample(("Babson",), samples=2, seed=1, forced={e.fixed[0].team: "win"})
        with self.assertRaises(ValueError):
            e.sample(("Babson", "Babson"), samples=2, seed=1)
        self.assertEqual(e.sample(("Babson",), samples=5, seed=11),
                         e.sample(("Babson",), samples=5, seed=11))

    def test_recent_npi_changes_probabilities_not_graph_fixed_point(self):
        e = self.evaluator()
        different = ScheduleEvaluator(self.games, self.ratings, "Amherst", e.fixed,
                                      (Candidate("Babson", 45.123456789),), self.model)
        self.assertNotEqual(e.probabilities["Babson"], different.probabilities["Babson"])
        self.assertEqual(e.sample(("Babson",), samples=2, seed=1, forced={"Babson": "win"}),
                         different.sample(("Babson",), samples=2, seed=1, forced={"Babson": "win"}))

    def test_real_end_to_end_ranking_and_serialization(self):
        config = default_config("2024")
        config.update(fixed_games=[{"team": t, "result": r} for t, r in self.historical if t != "Babson"],
                      candidates=[{"team": t, "probabilities": {"win": 1.0, "tie": 0.0, "loss": 0.0}}
                                  for t in ("Babson", "Springfield")],
                      bands=[], open_slots=1, samples=2, validation_samples=2,
                      insight_samples=2, top_n=2)
        report = rank_schedules(self.games, self.ratings, config)
        self.assertEqual(len(report["screening"]), 2)
        self.assertEqual(len(report["top_schedules"]), 2)
        first, second = report["top_schedules"]
        self.assertGreaterEqual(first["projection"]["mean"], second["projection"]["mean"])
        self.assertEqual(first["target_npi"], config["target_npi"])
        self.assertEqual(first["target_gap"]["mean"], first["projection"]["mean"]-config["target_npi"])
        self.assertTrue(0 <= first["target_hit_rate"] <= 1)
        self.assertEqual(first["projection"]["mean_standard_error"], 0.0)
        self.assertEqual(second["paired_gap_from_leader"]["mean"],
                         first["projection"]["mean"]-second["projection"]["mean"])
        self.assertEqual(first["logistics"]["total_travel_miles"], 0)
        self.assertEqual(len(first["logistics"]["games"]), 1)
        self.assertEqual(json.loads(json.dumps(report, allow_nan=False))["top_schedules"][0]["projection"],
                         first["projection"])
        text = render_report(report)
        self.assertIn("holdout outcomes did not enter fitting", text)
        self.assertIn("not mathematical bounds", text)
        self.assertIn("Win lift", text)
        config["max_combinations"] = 1
        with self.assertRaisesRegex(ValueError, "combinations exceeds"):
            rank_schedules(self.games, self.ratings, config)

    def test_quick_mode_still_converges_every_finalist(self):
        config = default_config("2024")
        config.update(fixed_games=[{"team": t, "result": r} for t, r in self.historical if t != "Babson"],
                      candidates=[{"team": "Babson"}, {"team": "Springfield"}], bands=[],
                      open_slots=1, samples=2, validation_samples=2, insight_samples=2,
                      top_n=2, analysis_mode="quick", include_standalone_insights=False)
        report = rank_schedules(self.games, self.ratings, config)
        self.assertEqual(report["calculation"]["screening"], "eight-pass division shortlist")
        self.assertEqual(report["calculation"]["finalists"], "full-division")
        self.assertEqual(report["standalone_opponents"], [])
        self.assertGreater(report["division_solves"], 0)


class TestSummary(unittest.TestCase):
    def test_precision_and_interpolated_range(self):
        x = 52.1234567890123
        result = summarize([x, x+2])
        self.assertEqual(result["mean"], x+1)
        self.assertAlmostEqual(result["p10"], x+.2, places=12)
        self.assertAlmostEqual(result["p90"], x+1.8, places=12)
        self.assertEqual(result["mean_standard_error"], 1.0)
        self.assertIsNone(summarize([x])["mean_standard_error"])


if __name__ == "__main__":
    unittest.main()
