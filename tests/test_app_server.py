"""The interactive app uses the verified model and strict local-only boundaries."""
from copy import deepcopy
import threading
import time
import unittest

from npi_model.app_server import AppState, validate_config
from npi_model.planning import default_config, load_graph
from npi_model.season_npi import SeasonGame, calculate_season_npi


class TestAppValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ratings, _ = load_graph()

    def test_defaults_and_real_rank_bands(self):
        config, summary = validate_config({}, self.ratings)
        self.assertEqual(summary['combinations'], 21)
        self.assertEqual(summary['fixed_count'], 10)
        self.assertEqual(config, default_config())
        config.update(mode='bands', band_scale='rank', open_slots=1,
                      bands=[{'label':'75-99', 'lower':75, 'upper':100}])
        _, summary = validate_config(config, self.ratings)
        self.assertEqual(summary['candidate_count'], 2)
        self.assertEqual(summary['bands'][0]['member_count'], 25)

    def test_rejects_strings_booleans_and_nonfinite_numbers(self):
        for key, value in [('samples', True), ('samples', '8'), ('open_slots', 1.5),
                           ('seed', float('nan')), ('probability_slope_scale', float('inf')),
                           ('target_npi', 101)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_config({key:value}, self.ratings)
        for bad in ('0.5', True, -1, float('nan')):
            with self.assertRaises(ValueError):
                validate_config({'candidates':[{'team':'Babson', 'probabilities':
                                 {'win':bad,'tie':.2,'loss':.3}}]}, self.ratings)

    def test_rejects_impossible_jobs_before_start(self):
        invalid = [{'open_slots':8}, {'max_combinations':20}, {'samples':100000},
                   {'required':['Tufts']}, {'required':['Babson'], 'excluded':['Babson']},
                   {'candidates':[{'team':'Imaginary club'}]}, {'typo':1},
                   {'fixed_games':None}, {'candidates':[{'team':'Babson','rating':50}]}]
        for config in invalid:
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_config(config, self.ratings)

    def test_probability_totals_and_locked_result_conflict(self):
        config=default_config()
        config['fixed_games'][0].update(result='win', probabilities={'win':1,'tie':0,'loss':0})
        with self.assertRaises(ValueError): validate_config(config, self.ratings)
        with self.assertRaises(ValueError):
            validate_config({'candidates':[{'team':'Babson','probabilities':
                             {'win':.8,'tie':.2,'loss':.2}}]},self.ratings)

    def test_practical_planning_fields_and_constraints(self):
        config=default_config()
        config.update(open_slots=2, required=[config['candidates'][0]['team']],
                      preferred=[config['candidates'][1]['team']],
                      max_total_travel_miles=500, max_total_cost=5000)
        config['candidates'][0].update(matchup='favorite', venue='home',
            probabilities={'win':.65,'tie':.20,'loss':.15},
            available_dates=['2027-09-01'], travel_miles=0, estimated_cost=500)
        config['candidates'][1].update(matchup='toss_up', venue='away',
            probabilities={'win':.40,'tie':.20,'loss':.40},
            available_dates=['2027-09-01','2027-09-08'], travel_miles=120,
            estimated_cost=1500)
        _, summary=validate_config(config,self.ratings)
        self.assertGreater(summary['combinations'],0)
        self.assertLessEqual(summary['combinations'],summary['unfiltered_combinations'])
        parsed=next(row for row in summary['candidates'] if row['team']==config['candidates'][0]['team'])
        self.assertEqual(parsed['venue'],'home')
        self.assertEqual(parsed['matchup'],'favorite')
        for patch in ({'venue':'neutral'}, {'available_dates':['09/01/27']},
                      {'estimated_cost':-1}, {'matchup':'favorite'}):
            bad=default_config();bad['candidates'][0].update(patch)
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                validate_config(bad,self.ratings)
        with self.assertRaises(ValueError):
            validate_config({'required':['Babson'],'preferred':['Babson']},self.ratings)
        conflict=default_config();conflict.update(open_slots=2,required=[conflict['candidates'][0]['team']])
        conflict['candidates'][0]['available_dates']=['2027-09-01']
        for row in conflict['candidates'][1:]:row['available_dates']=['2027-09-01']
        with self.assertRaisesRegex(ValueError,'No schedule fits'):
            validate_config(conflict,self.ratings)


class TestAppState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=AppState()

    def test_bootstrap_exposes_only_needed_public_data_and_reference(self):
        data=self.state.bootstrap()
        self.assertEqual(len(data['teams']),402)
        self.assertEqual(data['source']['cutoff'],'2025-11-09')
        self.assertEqual(data['config'],default_config())
        if data['report'] is not None:
            self.assertEqual(data['report']['config'],data['config'])
        comparison=self.state.bootstrap('2024')
        self.assertEqual(len(comparison['teams']),407)
        self.assertEqual(comparison['source']['cutoff'],'2024-10-27')
        self.assertEqual(data['model']['method'],'prior_season_out_of_time')
        amherst=next(t for t in data['teams'] if t['name']=='Amherst')
        self.assertEqual([row['season'] for row in amherst['history']],['2025','2024','2023','2022'])
        babson=next(t for t in data['teams'] if t['name']=='Babson')
        manhattanville=next(t for t in data['teams'] if t['name']=='Manhattanville')
        self.assertEqual(babson['matchup_outlook'],'toss_up')
        self.assertEqual(manhattanville['matchup_outlook'],'favorite')
        self.assertAlmostEqual(sum(babson['matchup_probabilities'].values()),1)
        with self.assertRaises(ValueError): self.state.bootstrap('../../private')
        with self.assertRaises(ValueError): self.state.validate({'season':True})

    def test_explorer_matches_season_rule_at_bonus_threshold(self):
        config=default_config()
        for row in config['fixed_games']: row['result']='win'
        baseline_games=[SeasonGame(g['team'],self.state.ratings[g['team']],g['result'])
                        for g in config['fixed_games']]
        for npi in (39.123456789,54,54.000000001,75):
            actual=self.state.explore({'config':config,'opponent_npi':npi})
            baseline=calculate_season_npi(baseline_games).npi
            self.assertEqual(actual['baseline_npi'],baseline)
            for outcome in ('win','tie','loss'):
                expected=calculate_season_npi(baseline_games+[SeasonGame('probe',npi,outcome)]).npi
                self.assertEqual(actual['outcomes'][outcome]['npi'],expected)
                self.assertEqual(actual['outcomes'][outcome]['impact'],expected-baseline)
        self.assertEqual(self.state.explore({'config':config,'opponent_npi':39})['outcomes']['win']['impact'],0)
        config['fixed_games'][-1]['result']='loss'
        self.assertLess(self.state.explore({'config':config,'opponent_npi':39})['outcomes']['win']['impact'],0)
        self.assertEqual(self.state.explore({'config':config,'opponent_npi':100})['outcomes']['loss']['impact'],0)

    def test_explorer_remains_available_for_an_incomplete_candidate_pool(self):
        config=default_config()
        config['candidates']=[]
        self.assertEqual(self.state.explore({'config':config,'opponent_npi':52.123456789})['opponent_npi'],52.123456789)
        for value in (True, '52', -1, 101):
            with self.assertRaises(ValueError): self.state.explore({'opponent_npi':value})

    def test_two_jobs_can_run_and_cancellation_stops_at_a_checkpoint(self):
        entered, release = threading.Event(), threading.Event()
        original=self.state.ranker
        def waiting_ranker(games, ratings, config, progress):
            entered.set()
            while not release.wait(.01):
                progress.checkpoint()
            progress('Scored schedule 1/21')
            return {'config':deepcopy(config)}
        self.state.ranker=waiting_ranker
        try:
            job_id=self.state.start({},owner='first')['id']
            self.assertTrue(entered.wait(2))
            second=self.state.start({},owner='second')['id']
            with self.assertRaises(RuntimeError): self.state.start({},owner='third')
            self.assertEqual(self.state.job(job_id,cancel=True,owner='first')['status'],'cancelled')
            deadline=time.monotonic()+1
            while job_id in self.state.active_jobs and time.monotonic()<deadline: time.sleep(.01)
            third=self.state.start({},owner='third')['id']
            self.assertEqual(self.state.job(second,owner='second')['status'],'running')
            self.assertEqual(self.state.job(third,owner='third')['status'],'running')
            release.set()
            deadline=time.monotonic()+3
            while self.state.active and time.monotonic()<deadline: time.sleep(.01)
            self.assertEqual(self.state.job(job_id,owner='first')['status'],'cancelled')
            self.assertIsNone(self.state.active)
            self.assertNotIn('cancel',self.state.job(job_id,owner='first'))
            def broken(*args, **kwargs): raise ValueError('Expected test failure')
            self.state.ranker=broken
            failed=self.state.start({})['id']
            deadline=time.monotonic()+3
            while self.state.active and time.monotonic()<deadline: time.sleep(.01)
            self.assertEqual(self.state.job(failed)['status'],'error')
        finally:
            release.set()
            self.state.ranker=original


if __name__=='__main__': unittest.main()
