"""Result freshness is explicit, and failed fetches never become fresh results."""

import unittest
from unittest.mock import patch
from urllib.error import URLError

from npi_model import nescac_sync as sync


class TestResultsFreshness(unittest.TestCase):
    def setUp(self):
        self.cache = dict(sync._cache)
        self.status = dict(sync._status)
        sync._cache.clear()
        sync._status.clear()

    def tearDown(self):
        sync._cache.clear()
        sync._cache.update(self.cache)
        sync._status.clear()
        sync._status.update(self.status)

    def test_cached_results_keep_their_original_fetch_time(self):
        game = sync.SyncedGame('Tufts', 'win', 'Oct 1', '2-1')
        sync._cache[2026] = (1000, [game])
        with patch.object(sync.time, 'time', return_value=1200), patch.object(sync, 'urlopen') as network:
            result = sync.sync_summary(2026)
        network.assert_not_called()
        self.assertTrue(result['cached'])
        self.assertFalse(result['stale'])
        self.assertEqual(result['fetched_at'], sync._timestamp(1000))
        self.assertEqual(result['checked_at'], sync._timestamp(1200))
        self.assertEqual(result['year'], 2026)
        self.assertIsNone(result['error'])

    def test_failure_retains_old_success_time_and_labels_cached_scores_stale(self):
        game = sync.SyncedGame('Tufts', 'win', 'Oct 1', '2-1')
        sync._cache[2026] = (1000, [game])
        with patch.object(sync.time, 'time', return_value=20000), patch.object(sync, 'urlopen', side_effect=URLError('offline')):
            result = sync.sync_summary(2026)
        self.assertIn('offline', result['error'])
        self.assertTrue(result['stale'])
        self.assertFalse(result['cached'])
        self.assertEqual(result['fetched_at'], sync._timestamp(1000))
        self.assertEqual(result['results'][0]['result'], 'win')
        self.assertEqual(sync._cache[2026][0], 1000)

    def test_first_failure_does_not_claim_a_successful_fetch(self):
        with patch.object(sync, 'urlopen', side_effect=URLError('offline')):
            result = sync.sync_summary(2025)
        self.assertIsNone(result['fetched_at'])
        self.assertEqual(result['results'], [])
        self.assertFalse(result['stale'])
        self.assertIn('/2025', result['source'])

    def test_changed_markup_is_a_failure_instead_of_a_false_empty_success(self):
        with self.assertRaisesRegex(ValueError, 'No recognizable'):
            sync._parse('<html><p>Service unavailable</p></html>')

    def test_repeated_opponents_require_review_instead_of_silent_overwrite(self):
        entry = '''<li class="sidearm-schedule-game W">
          <span class="sidearm-schedule-game-conference">NESCAC</span>
          <span class="sidearm-schedule-game-opponent-name">Tufts University</span>
        </li>'''
        self.assertEqual(sync._parse(entry)[0].result, 'win')
        with self.assertRaisesRegex(ValueError, 'rematches'):
            sync._parse(entry+entry)


if __name__ == '__main__':
    unittest.main()
