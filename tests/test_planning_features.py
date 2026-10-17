"""Forecast timing, fixed-shortlist sensitivity, and portable input integrity."""

from copy import deepcopy
from dataclasses import asdict
import json
import threading
import time
import unittest
from unittest.mock import patch

from npi_model.app_server import AppState, validate_config
from npi_model.backtest import planning_backtest, planning_test_rows
from npi_model.planning import Candidate, default_config, parse_plan
from npi_model.schedule_optimizer import ScheduleEvaluator, rank_schedules
from npi_model.seasons import load_season, planning_ratings
from npi_model.sensitivity import compare_assumptions, validate_shortlist
from npi_model.temporal_model import historical_model


class TestPlanningBacktest(unittest.TestCase):
    def test_replay_uses_production_blend_and_probability_function(self):
        report = planning_backtest('2025')
        self.assertEqual([row['season'] for row in report['strength_sources']], ['2024', '2023', '2022'])
        self.assertEqual([row['weight'] for row in report['strength_sources']], [.5, .3, .2])
        self.assertEqual(report['training_seasons'], ['2023', '2024'])
        self.assertEqual(report['model']['games'], 3528)
        strengths = planning_ratings('2024')
        self.assertAlmostEqual(strengths['Babson'], .5*load_season('2024')[1]['Babson']
                               +.3*load_season('2023')[1]['Babson']+.2*load_season('2022')[1]['Babson'])
        rows, _, _ = planning_test_rows('2025')
        model, _ = historical_model('2025')
        _, ratings, games = load_season('2024')
        evaluator = ScheduleEvaluator(games, ratings, 'Amherst', (),
                                      (Candidate('Babson', strengths['Babson']),), model,
                                      target_recent_npi=strengths['Amherst'], probability_ratings=strengths)
        self.assertEqual(asdict(evaluator.probabilities['Babson']),
                         asdict(model.predict(strengths['Amherst'], strengths['Babson'])))
        game = load_season('2025')[2][0]
        self.assertEqual(rows[0][0], (strengths[game.team_a]-strengths[game.team_b])/10)
        self.assertEqual(sum(row['count'] for row in report['model']['win_calibration']), 7056)
        self.assertFalse(planning_backtest('2023')['available'])
        self.assertFalse(planning_backtest('2024')['complete_three_season_blend'])

    def test_test_season_ratings_do_not_enter_planning_inputs(self):
        expected, _, _ = planning_test_rows('2025')
        real_load = load_season
        def changed_ratings(year):
            data, ratings, games = real_load(year)
            return (data, {team: 99 for team in ratings}, games) if year == '2025' else (data, ratings, games)
        with patch('npi_model.backtest.load_season', side_effect=changed_ratings):
            actual, _, _ = planning_test_rows('2025')
        self.assertEqual(actual, expected)

    def test_future_dated_predictor_is_rejected(self):
        real_load = load_season
        def future_snapshot(year):
            data, ratings, games = real_load(year)
            if year == '2024':
                data = deepcopy(data);data['source']['cutoff'] = '2026-01-01'
            return data, ratings, games
        with patch('npi_model.backtest.load_season', side_effect=future_snapshot):
            with self.assertRaisesRegex(ValueError, 'before the first test game'):
                planning_test_rows('2025')


class TestSensitivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ratings, cls.games = load_season('2024')

    def config(self):
        config = default_config('2024')
        config.update(candidates=[{'team': 'Babson'}, {'team': 'WPI'}], open_slots=1,
                      samples=2, validation_samples=2, insight_samples=2, top_n=2,
                      convergence_tolerance=1e-8, include_standalone_insights=False)
        config['playoff_games'] = [{'game_id': 'playoff:quarterfinal', 'team': 'Tufts',
                                   'round': 'Quarterfinal', 'result': 'loss'}]
        return config

    def test_same_shortlist_all_three_profiles_and_input_data_unchanged(self):
        config = self.config()
        before = deepcopy(config)
        ratings_before, games_before = dict(self.ratings), tuple(self.games)
        result = compare_assumptions(self.games, self.ratings, config, [['Babson'], ['WPI']], shift=3)
        self.assertEqual([row['key'] for row in result['profiles']], ['cautious', 'baseline', 'optimistic'])
        self.assertEqual([row['effective_shift'] for row in result['profiles']], [-3, 0, 3])
        for profile in result['profiles']:
            self.assertEqual([row['opponents'] for row in profile['schedules']], [['Babson'], ['WPI']])
            for row in profile['schedules']:
                self.assertGreaterEqual(row['target_hit_rate'], 0)
                self.assertLessEqual(row['target_hit_rate'], 1)
        for row in result['schedules']:
            cases = [p['schedules'][row['option']-1] for p in result['profiles']]
            self.assertEqual(row['largest_gap_to_leader'], max(case['gap_from_leader']['mean'] for case in cases))
        self.assertEqual(config, before)
        self.assertEqual(self.ratings, ratings_before)
        self.assertEqual(tuple(self.games), games_before)

    def test_entered_probabilities_and_rematch_result_are_never_overridden(self):
        config = self.config()
        config['candidates'][0].update(matchup='custom', probabilities={'win': 1, 'tie': 0, 'loss': 0})
        result = compare_assumptions(self.games, self.ratings, config, [['Babson']], shift=10)
        means = [profile['schedules'][0]['projection']['mean'] for profile in result['profiles']]
        self.assertEqual(means, [means[0]]*3)
        target, fixed, candidates, _ = parse_plan(config, self.ratings)
        evaluator = ScheduleEvaluator(self.games, self.ratings, target, fixed, candidates, historical_model('2024')[0])
        self.assertEqual(means[0], evaluator.sample(('Babson',), samples=2, seed=3)[0])

    def test_baseline_reuses_the_main_finalist_draws(self):
        config = self.config()
        config['validation_samples'] = 8
        main = rank_schedules(self.games, self.ratings, config)
        schedules = [list(row['opponents']) for row in main['top_schedules']]
        sensitivity = compare_assumptions(self.games, self.ratings, config, schedules)
        baseline = next(profile for profile in sensitivity['profiles'] if profile['key'] == 'baseline')
        for original, replay in zip(main['top_schedules'], baseline['schedules']):
            self.assertAlmostEqual(original['projection']['mean'], replay['projection']['mean'], places=6)
            self.assertEqual(original['target_hit_rate'], replay['target_hit_rate'])

    def test_shortlist_validation_keeps_logistics_and_required_opponents(self):
        config = self.config()
        for schedules, shift in (([['Tufts']], 3), ([['Babson', 'Babson']], 3),
                                 ([['Babson'], ['Babson']], 3), ([['Babson']], True),
                                 ([['Babson']], float('nan')), ([['Babson']], 0)):
            with self.subTest(schedules=schedules, shift=shift), self.assertRaises(ValueError):
                validate_shortlist(config, self.ratings, schedules, shift)
        config['required'] = ['WPI']
        with self.assertRaises(ValueError):validate_shortlist(config, self.ratings, [['Babson']], 3)
        config['required'] = []
        config['max_total_cost'] = 1
        config['candidates'][0]['estimated_cost'] = 2
        with self.assertRaises(ValueError):validate_shortlist(config, self.ratings, [['Babson']], 3)


class TestPortablePlans(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = AppState()

    def test_roundtrip_preserves_inputs_and_provenance(self):
        config = default_config()
        config['playoff_games'] = [{'team': 'Tufts', 'game_id': 'playoff:quarterfinal',
                                   'round': 'Quarterfinal', 'result': 'tie', 'decision': 'advanced_on_penalties'}]
        config['candidates'][0].update(matchup='custom', probabilities={'win': 1, 'tie': 0, 'loss': 0})
        before = deepcopy(config)
        file = self.state.export_plan({'name': 'Quarterfinal plan', 'config': config})
        result = self.state.import_plan(json.loads(json.dumps(file)))
        self.assertEqual(result['config'], config)
        self.assertEqual(result['name'], 'Quarterfinal plan')
        self.assertTrue(result['data_matches'])
        self.assertEqual(config, before)
        self.assertEqual(set(file['data']['sources']), {'2022', '2023', '2024', '2025'})
        self.assertNotIn('top_schedules', file)

    def test_different_data_is_disclosed_and_old_optional_fields_are_normalized(self):
        file = self.state.export_plan({'name': 'Older plan', 'config': default_config()})
        file['data']['sources']['2025']['sha256'] = '0'*64
        for key in ('playoff_games', 'historical_cutoff_npi', 'results_updated'):
            file['config'].pop(key)
        result = self.state.import_plan(file)
        self.assertFalse(result['data_matches'])
        self.assertTrue(any('different data version' in note for note in result['notices']))
        self.assertEqual(result['config']['playoff_games'], [])

    def test_invalid_files_cannot_bypass_normal_plan_validation(self):
        file = self.state.export_plan({'name': 'Valid', 'config': default_config()})
        for patch_value in ({'version': True}, {'version': 2}, {'format': 'other'},
                            {'name': ''}, {'exported_at': 'not a date'}, {'data': []},
                            {'config': {'season': '2025', 'fixed_games': None}},
                            {'config': {'season': '2025', 'candidates': [{'team': 'Unknown team'}]}}):
            with self.subTest(patch_value=patch_value), self.assertRaises(ValueError):
                self.state.import_plan({**deepcopy(file), **patch_value})
        with self.assertRaises(ValueError): self.state.import_plan({'config': default_config()})

    def test_sensitivity_jobs_use_existing_ownership_and_cancellation(self):
        entered = threading.Event()
        def waiting(games, ratings, config, schedules, shift, progress):
            entered.set()
            while True:
                time.sleep(.005);progress.checkpoint()
        state = AppState(assumption_ranker=waiting)
        config = default_config();config.update(candidates=[{'team': 'Babson'}], open_slots=1)
        job = state.start_sensitivity({'config': config, 'schedules': [['Babson']]}, owner='coach')['id']
        self.assertTrue(entered.wait(2))
        with self.assertRaises(KeyError):state.job(job, owner='other')
        self.assertEqual(state.job(job, owner='coach', cancel=True)['status'], 'cancelled')
        deadline = time.monotonic()+2
        while state.active and time.monotonic()<deadline:time.sleep(.01)
        self.assertIsNone(state.active)


if __name__ == '__main__':unittest.main()
