"""Offline tests for /api/player/<uid>/career."""
import os
import tempfile
import unittest

from flask import Flask

from models import (
    ChartDataCache,
    Event,
    MonthlyChartPoint,
    MonthlyRanking,
    MonthlyScore,
    PlayerDegree,
    PlayerScoreHistory,
    Score,
    db,
)
from routes.player import player_bp
from services.player_career_service import career_cache, clear_career_cache
from services.timeutil import now_ms
from services.ttl_cache import TTLCache


class PlayerCareerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(self.tmpdir.name, 'test.db')
        self.app.config['SQLALCHEMY_BINDS'] = {'degrees': 'sqlite:///:memory:'}
        db.init_app(self.app)
        self.app.register_blueprint(player_bp, url_prefix='/api/player')

        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        clear_career_cache()
        self._seed()

    def tearDown(self):
        db.session.remove()
        for engine in db.engines.values():
            engine.dispose()
        self.context.pop()
        self.tmpdir.cleanup()
        clear_career_cache()

    def _seed(self):
        db.session.add_all([
            Event(event_id='348', name='Rock!Lock!Rock!', event_type='mission_live', start_at=1000, end_at=5000),
            Event(event_id='329', name='Beyond my Imagination', event_type='versus', start_at=100, end_at=900),
            Event(event_id='5001', name='Dummy', event_type='versus', start_at=100, end_at=200),
        ])
        db.session.add_all([
            Score(event_id='348', uid='101', name='Top1', pt=50000000, rank=1, signature=''),
            Score(event_id='348', uid='2438296', name='[sub]ちえる', pt=38000000, rank=2, signature='gg'),
            Score(event_id='329', uid='2438296', name='[sub]', pt=200000000, rank=1, signature='win'),
            Score(event_id='329', uid='102', name='Second', pt=185000000, rank=2, signature=''),
            Score(event_id='5001', uid='2438296', name='Ignore', pt=999, rank=1, signature=''),
        ])
        db.session.add(ChartDataCache(event_id='348', uid='2438296', bucket_interval='15m', bucket_ts=2000, pt=1000))
        db.session.add(PlayerDegree(uid='2438296', event_id='210', rank=5, degree_id=50))

        db.session.add(MonthlyRanking(monthly_id=25, name='2026年11月', start_at=1000, end_at=9000))
        db.session.add_all([
            MonthlyScore(monthly_id=25, uid='999', name='M1', pt=9000000, rank=1, signature=''),
            MonthlyScore(monthly_id=25, uid='2438296', name='[sub]ちえる', pt=7500000, rank=2, signature='m2', degree_id=8001),
        ])
        db.session.add(MonthlyChartPoint(monthly_id=25, uid='2438296', name='[sub]ちえる', timestamp=2000, pt=1000))
        db.session.commit()

    def test_player_career_merges_events_degrees_and_monthly(self):
        resp = self.app.test_client().get('/api/player/2438296/career')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertEqual(data['uid'], '2438296')
        self.assertEqual([e['event_id'] for e in data['events']], ['348', '329', '210'])

        ev348 = data['events'][0]
        self.assertEqual(ev348['rank'], 2)
        self.assertEqual(ev348['gap_to_first'], 12000000)
        self.assertEqual(ev348['gap_to_prev'], 12000000)
        self.assertIsNone(ev348['lead_to_second'])
        self.assertEqual(ev348['top1_uid'], '101')
        self.assertIsNone(ev348['top10_uid'])
        self.assertEqual(ev348['name_used'], '[sub]ちえる')
        self.assertEqual(ev348['signature'], 'gg')
        self.assertTrue(ev348['has_local_detail'])
        self.assertTrue(ev348['has_chart'])

        ev329 = data['events'][1]
        self.assertEqual(ev329['rank'], 1)
        self.assertEqual(ev329['gap_to_first'], 0)
        self.assertEqual(ev329['lead_to_second'], 15000000)
        self.assertEqual(ev329['top1_uid'], '2438296')
        self.assertIsNone(ev329['top10_uid'])
        self.assertEqual(ev329['name_used'], '[sub]')
        self.assertFalse(ev329['has_chart'])

        ev210 = data['events'][2]
        self.assertFalse(ev210['has_local_detail'])
        self.assertEqual(ev210['rank'], 5)

        self.assertEqual(len(data['monthly']), 1)
        m25 = data['monthly'][0]
        self.assertEqual(m25['monthly_id'], 25)
        self.assertEqual(m25['rank'], 2)
        self.assertEqual(m25['gap_to_first'], 1500000)
        self.assertEqual(m25['top1_uid'], '999')
        self.assertIsNone(m25['top10_uid'])
        self.assertEqual(m25['degree_id'], 8001)
        self.assertTrue(m25['has_chart'])

    def test_top10_uid_selected_when_ten_ranks_exist(self):
        for rank in range(3, 11):
            db.session.add(Score(
                event_id='348',
                uid=str(200 + rank),
                name=f'P{rank}',
                pt=40000000 - rank * 1000000,
                rank=rank,
                signature='',
            ))
        db.session.commit()
        clear_career_cache()

        resp = self.app.test_client().get('/api/player/2438296/career')
        self.assertEqual(resp.status_code, 200)
        ev348 = resp.get_json()['events'][0]
        self.assertEqual(ev348['top1_uid'], '101')
        self.assertEqual(ev348['top10_uid'], '210')

    def test_unknown_player_returns_empty_lists(self):
        resp = self.app.test_client().get('/api/player/123456789/career')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.get_json(),
            {'uid': '123456789', 'events': [], 'monthly': []},
        )
        # Empty career payloads must not pollute career_cache
        self.assertNotIn('123456789', career_cache._data)

    def test_has_chart_aligns_with_15m_cache_and_old_event_pruning(self):
        now = now_ms()
        # Old ended event (>24h ago) with only raw history and 1h cache -> has_chart False
        db.session.add(Event(event_id='300', name='Old Pruned', event_type='versus', start_at=1000, end_at=5000))
        db.session.add(Score(event_id='300', uid='7777', name='P', pt=1000000, rank=1, signature=''))
        db.session.add(ChartDataCache(event_id='300', uid='7777', bucket_interval='1h', bucket_ts=2000, pt=500000))
        db.session.add(PlayerScoreHistory(event_id='300', uid='7777', name='P', pt=1000000, timestamp=4900))

        # Active/recent event with only raw history -> has_chart True
        db.session.add(Event(event_id='350', name='Recent Active', event_type='versus', start_at=now - 3600_000, end_at=now + 3600_000))
        db.session.add(Score(event_id='350', uid='7777', name='P', pt=2000000, rank=1, signature=''))
        db.session.add(PlayerScoreHistory(event_id='350', uid='7777', name='P', pt=2000000, timestamp=now - 60_000))
        db.session.commit()
        clear_career_cache()

        resp = self.app.test_client().get('/api/player/7777/career')
        self.assertEqual(resp.status_code, 200)
        by_eid = {e['event_id']: e for e in resp.get_json()['events']}
        self.assertFalse(by_eid['300']['has_chart'])
        self.assertTrue(by_eid['350']['has_chart'])

    def test_ttl_cache_maxsize_evicts_oldest(self):
        cache = TTLCache(60, maxsize=2)
        cache.set('a', 1)
        cache.set('b', 2)
        cache.set('c', 3)
        self.assertEqual(len(cache._data), 2)
        self.assertIsNone(cache.get('a'))
        self.assertEqual(cache.get('b'), 2)
        self.assertEqual(cache.get('c'), 3)


if __name__ == '__main__':
    unittest.main()
