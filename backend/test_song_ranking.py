"""Offline unit tests for Song Ranking (歌榜) T10: python -m unittest test_song_ranking.py."""
import json
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from models import Event, EventSongRanking, PlayerSongDegree, Score, db
from routes import events as events_route
from routes.events import events_bp
from routes.player import player_bp
from services import song_ranking_service as srs
from services.event_repository import serialize_event
from services.player_career_service import clear_career_cache, get_player_career


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


class SongRankingTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_BINDS'] = {'degrees': 'sqlite:///:memory:'}
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.register_blueprint(events_bp, url_prefix='/api/events')
        app.register_blueprint(player_bp, url_prefix='/api/player')
        db.init_app(app)
        self.app = app
        self.client = app.test_client()
        self.context = app.app_context()
        self.context.push()
        db.create_all()

        srs._active_cache.clear()
        srs._event_musics_cache.clear()
        srs._event_rewards_cache.clear()
        srs._songs_title_cache.clear()
        events_route._last_song_ranking_refresh_time.clear()
        clear_career_cache()

        now = srs.now_ms()
        self.active_challenge = Event(
            event_id='347', name='Active Challenge', event_type='challenge',
            start_at=now - 3600_000, end_at=now + 3600_000,
        )
        self.ended_medley = Event(
            event_id='341', name='Ended Medley', event_type='medley',
            start_at=now - 7200_000, end_at=now - 3600_000,
        )
        self.ended_live_try = Event(
            event_id='346', name='Ended Live Try', event_type='live_try',
            start_at=now - 7200_000, end_at=now - 3600_000,
        )
        db.session.add_all([self.active_challenge, self.ended_medley, self.ended_live_try])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        for engine in db.engines.values():
            engine.dispose()
        self.context.pop()

    def test_serialize_event_has_song_ranking_flag(self):
        self.assertTrue(serialize_event(self.active_challenge)['has_song_ranking'])
        self.assertTrue(serialize_event(self.ended_medley)['has_song_ranking'])
        self.assertFalse(serialize_event(self.ended_live_try)['has_song_ranking'])

    def test_active_challenge_multi_song_proxy_and_302_fallback(self):
        meta = {'musics': [[{'musicId': 826}, {'musicId': 650}]]}
        songs_all = {
            '826': {'musicTitle': ['Song A']},
            '650': {'musicTitle': ['Song B']},
        }
        top_826 = {
            'points': [
                {'time': 1000, 'uid': 111, 'value': 3900000},
                {'time': 1000, 'uid': 222, 'value': 3800000},
                {'time': 900, 'uid': 999, 'value': 4000000},  # stale timestamp ignored
            ],
            'users': [
                {'uid': 111, 'name': 'P1', 'introduction': 'hi'},
                {'uid': 222, 'name': 'P2', 'introduction': ''},
            ],
        }
        top_650 = {
            'points': [{'time': 2000, 'uid': 333, 'value': 2500000}],
            'users': [{'uid': 333, 'name': 'P3'}],
        }

        def fake_get(url, params=None, timeout=15, allow_redirects=True):
            if url == srs.BESTDORI_SONGS_URL:
                return _mock_response(200, songs_all)
            if url == srs.EVENT_TOP_API_URL and not allow_redirects:
                # Simulate 302 redirect on primary tracker -> must fallback to Bestdori
                return _mock_response(302, None)
            if url == srs.BESTDORI_EVENT_TOP_URL:
                if params['mid'] == 826:
                    return _mock_response(200, top_826)
                if params['mid'] == 650:
                    return _mock_response(200, top_650)
            return _mock_response(404, None)

        with patch.object(srs.bestdori_client, 'get_event_meta', return_value=meta), \
             patch.object(srs.bestdori_client.session, 'get', side_effect=fake_get):
            res = self.client.get('/api/events/347/song_ranking')

        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body['event_id'], 347)
        self.assertTrue(body['has_song_ranking'])
        self.assertTrue(body['is_active'])
        self.assertEqual(body['source'], 'live')
        self.assertEqual(len(body['songs']), 2)
        self.assertEqual(body['songs'][0]['music_id'], 826)
        self.assertEqual(body['songs'][0]['music_title'], 'Song A')
        self.assertEqual([e['uid'] for e in body['songs'][0]['entries']], [111, 222])
        self.assertEqual(body['songs'][0]['entries'][0]['gap'], 0)
        self.assertEqual(body['songs'][0]['entries'][1]['gap'], 100000)
        # Zero DB writes for active events
        self.assertEqual(EventSongRanking.query.count(), 0)

    def test_ended_medley_lazy_backfill_then_db_read(self):
        medley_payload = {
            'points': [{'time': 5000, 'uid': 777, 'value': 9100000}],
            'users': [{'uid': 777, 'name': 'MedleyKing', 'introduction': 'gg'}],
        }
        medley_meta = {'musics': [[{'musicId': 773, 'musicRankingRewards': [
            {'fromRank': 1, 'toRank': 1, 'resourceType': 'degree', 'resourceId': 10007},
        ]}]]}
        with patch.object(srs.bestdori_client, 'get_event_meta', return_value=medley_meta), \
             patch.object(srs.bestdori_client.session, 'get', return_value=_mock_response(200, medley_payload)) as mock_get:
            res1 = self.client.get('/api/events/341/song_ranking')
            self.assertEqual(res1.status_code, 200)
            b1 = res1.get_json()
            self.assertEqual(b1['source'], 'backfill')
            self.assertFalse(b1['is_active'])
            self.assertEqual(len(b1['songs']), 1)
            self.assertEqual(b1['songs'][0]['music_id'], -1)
            self.assertTrue(b1['songs'][0]['is_medley_aggregate'])
            self.assertEqual(b1['songs'][0]['entries'][0]['score'], 9100000)
            self.assertEqual(b1['songs'][0]['entries'][0]['degree_id'], 10007)
            self.assertEqual(mock_get.call_count, 1)

            # Second request must read from DB without calling upstream
            res2 = self.client.get('/api/events/341/song_ranking')
            self.assertEqual(res2.status_code, 200)
            b2 = res2.get_json()
            self.assertEqual(b2['source'], 'db')
            self.assertEqual(mock_get.call_count, 1)

        row = EventSongRanking.query.filter_by(event_id=341, music_id=-1).first()
        self.assertIsNotNone(row)
        self.assertEqual(json.loads(row.entries_json)[0]['uid'], 777)
        psd = PlayerSongDegree.query.filter_by(event_id=341, music_id=-1, uid='777').first()
        self.assertIsNotNone(psd)
        self.assertEqual(psd.degree_id, 10007)
        self.assertEqual(psd.score, 9100000)

    def test_event_without_song_ranking_returns_none_source(self):
        res = self.client.get('/api/events/346/song_ranking')
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertFalse(body['has_song_ranking'])
        self.assertEqual(body['source'], 'none')
        self.assertEqual(body['songs'], [])

    def test_backfill_ended_song_rankings_skips_already_persisted(self):
        db.session.add(EventSongRanking(event_id=341, music_id=-1, entries_json='[]', updated_at=1))
        db.session.commit()
        with patch.object(srs, 'persist_ended_event_song_ranking') as mock_persist:
            count = srs.backfill_ended_song_rankings(sleep_seconds=0)
        self.assertEqual(count, 0)
        mock_persist.assert_not_called()

    def test_player_career_includes_song_ranking_records(self):
        # Player 111 has both 肝榜 (Score) and 歌榜 (Challenge + Medley)
        db.session.add(Score(event_id='347', uid='111', name='BothPlayer', pt=5000000, rank=3))
        db.session.add(EventSongRanking(
            event_id=347, music_id=826, music_title='Song A',
            entries_json=json.dumps([
                {'rank': 1, 'uid': 111, 'name': 'BothPlayer', 'score': 7968249, 'gap': 0, 'degree_id': 10201, 'introduction': ''},
                {'rank': 2, 'uid': 1110, 'name': 'SubstringTrap', 'score': 7000000, 'gap': 968249, 'degree_id': 10202, 'introduction': ''},
            ]),
            updated_at=1794139199000,
        ))
        db.session.add(EventSongRanking(
            event_id=341, music_id=-1, music_title=None,
            entries_json=json.dumps([
                {'rank': 4, 'uid': 111, 'name': 'BothPlayerOld', 'score': 12500000, 'gap': 1000, 'degree_id': 10010, 'introduction': ''},
                {'rank': 5, 'uid': 888, 'name': 'SongOnly', 'score': 12400000, 'gap': 100000, 'degree_id': 10010, 'introduction': ''},
            ]),
            updated_at=1789012798461,
        ))
        db.session.commit()

        synced = srs.sync_all_player_song_degrees_from_rankings()
        self.assertEqual(synced, 2)

        # Combined player via HTTP route — must make ZERO external HTTP calls
        with patch.object(srs.bestdori_client.session, 'get', side_effect=AssertionError('unexpected HTTP')):
            res = self.client.get('/api/player/111/career')
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(len(body['events']), 1)
        self.assertEqual(len(body['song_ranking_records']), 2)
        self.assertEqual(body['song_ranking_records'][0]['event_id'], 347)
        self.assertEqual(body['song_ranking_records'][0]['music_id'], 826)
        self.assertEqual(body['song_ranking_records'][0]['music_title'], 'Song A')
        self.assertEqual(body['song_ranking_records'][0]['degree_id'], 10201)
        self.assertFalse(body['song_ranking_records'][0]['is_medley_aggregate'])
        self.assertEqual(body['song_ranking_records'][1]['event_id'], 341)
        self.assertEqual(body['song_ranking_records'][1]['degree_id'], 10010)
        self.assertTrue(body['song_ranking_records'][1]['is_medley_aggregate'])

        # Song-ranking-only player (no 肝榜 or monthly records)
        song_only = get_player_career(888)
        self.assertEqual(song_only['events'], [])
        self.assertEqual(song_only['monthly'], [])
        self.assertEqual(len(song_only['song_ranking_records']), 1)
        self.assertEqual(song_only['song_ranking_records'][0]['name'], 'SongOnly')
        self.assertEqual(song_only['song_ranking_records'][0]['rank'], 5)

        # Ensure substring uid '111' did not match '1110'
        trap = get_player_career(1110)
        self.assertEqual(len(trap['song_ranking_records']), 1)
        self.assertEqual(trap['song_ranking_records'][0]['rank'], 2)

    def test_resolve_song_degree_id_for_challenge_versus_and_medley(self):
        challenge_meta = {
            'musics': [[
                {
                    'musicId': 826,
                    'musicRankingRewards': [
                        {'fromRank': 1, 'toRank': 1, 'resourceType': 'degree', 'resourceId': 10201},
                        {'fromRank': 2, 'toRank': 2, 'resourceType': 'degree', 'resourceId': 10202},
                        {'fromRank': 3, 'toRank': 3, 'resourceType': 'degree', 'resourceId': 10203},
                        {'fromRank': 4, 'toRank': 10, 'resourceType': 'degree', 'resourceId': 10204},
                    ],
                },
                {
                    'musicId': 650,
                    'musicRankingRewards': [
                        {'fromRank': 1, 'toRank': 1, 'resourceType': 'degree', 'resourceId': 10205},
                    ],
                },
            ]]
        }
        medley_meta = {
            'musics': [[
                {
                    'musicId': 773,
                    'musicRankingRewards': [
                        {'fromRank': 1, 'toRank': 1, 'resourceType': 'degree', 'resourceId': 10007},
                        {'fromRank': 4, 'toRank': 10, 'resourceType': 'degree', 'resourceId': 10010},
                    ],
                },
            ]]
        }
        versus_meta = {
            'musics': [[
                {
                    'musicId': 822,
                    'musicRankingRewards': [
                        {'fromRank': 1, 'toRank': 1, 'resourceType': 'degree', 'resourceId': 10150},
                    ],
                },
            ]]
        }

        def fake_meta(eid):
            return {'347': challenge_meta, '341': medley_meta, '344': versus_meta}.get(str(eid))

        with patch.object(srs.bestdori_client, 'get_event_meta', side_effect=fake_meta):
            self.assertEqual(srs.resolve_song_degree_id(347, 826, 1), 10201)
            self.assertEqual(srs.resolve_song_degree_id(347, 826, 7), 10204)
            self.assertEqual(srs.resolve_song_degree_id(347, 650, 1), 10205)
            self.assertEqual(srs.resolve_song_degree_id(341, -1, 1), 10007)
            self.assertEqual(srs.resolve_song_degree_id(341, -1, 5), 10010)
            self.assertEqual(srs.resolve_song_degree_id(344, 822, 1), 10150)
            self.assertIsNone(srs.resolve_song_degree_id(344, 822, 11))

    def test_upstream_failure_does_not_poison_db_or_wipe_existing_archive(self):
        # 1. Upstream returns 500 for uncached ended event -> must not write empty row
        with patch.object(srs.bestdori_client.session, 'get', return_value=_mock_response(500, None)):
            res = self.client.get('/api/events/341/song_ranking')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['source'], 'none')
        self.assertEqual(EventSongRanking.query.count(), 0)

        # 2. Seed valid archived snapshot + degree, then force refresh during upstream outage
        db.session.add(EventSongRanking(
            event_id=341, music_id=-1, music_title=None,
            entries_json=json.dumps([
                {'rank': 1, 'uid': 777, 'name': 'MedleyKing', 'score': 9100000, 'gap': 0, 'degree_id': 10007, 'introduction': ''},
            ]),
            updated_at=5000,
        ))
        db.session.add(PlayerSongDegree(
            event_id=341, music_id=-1, uid='777', name='MedleyKing',
            rank=1, score=9100000, degree_id=10007, updated_at=5000,
        ))
        db.session.commit()

        with patch.object(srs.bestdori_client.session, 'get', return_value=_mock_response(500, None)):
            res2 = self.client.get('/api/events/341/song_ranking?force=true')
        self.assertEqual(res2.status_code, 200)
        body2 = res2.get_json()
        self.assertEqual(body2['source'], 'db')
        self.assertEqual(body2['songs'][0]['entries'][0]['uid'], 777)
        self.assertEqual(PlayerSongDegree.query.filter_by(event_id=341, music_id=-1, uid='777').count(), 1)

    def test_grace_period_serves_live_cache_without_premature_archive(self):
        now = srs.now_ms()
        just_ended = Event(
            event_id='349', name='Just Ended Medley', event_type='medley',
            start_at=now - 7200_000, end_at=now - 5 * 60_000,
        )
        db.session.add(just_ended)
        db.session.commit()

        payload = {
            'points': [{'time': now - 6 * 60_000, 'uid': 555, 'value': 8000000}],
            'users': [{'uid': 555, 'name': 'GracePlayer'}],
        }
        with patch.object(srs.bestdori_client, 'get_event_meta', return_value={}), \
             patch.object(srs.bestdori_client.session, 'get', return_value=_mock_response(200, payload)):
            res = self.client.get('/api/events/349/song_ranking')
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body['source'], 'live')
        self.assertFalse(body['is_active'])
        self.assertEqual(EventSongRanking.query.filter_by(event_id=349).count(), 0)

        # Backfill job must also skip events still inside grace period
        with patch.object(srs, 'persist_ended_event_song_ranking') as mock_persist:
            # Mark 341 already persisted so only 349 could be a candidate
            db.session.add(EventSongRanking(event_id=341, music_id=-1, entries_json='[{"uid":1}]', updated_at=1))
            db.session.commit()
            srs.backfill_ended_song_rankings(sleep_seconds=0)
        mock_persist.assert_not_called()

    def test_primary_empty_points_and_interval_fallback(self):
        meta = {'musics': [[{'musicId': 826}]]}
        songs_all = {'826': {'musicTitle': ['Song A']}}
        top_1m = {
            'points': [{'time': 1000, 'uid': 111, 'value': 3900000}],
            'users': [{'uid': 111, 'name': 'P1'}],
        }

        def fake_get(url, params=None, timeout=15, allow_redirects=True):
            if url == srs.BESTDORI_SONGS_URL:
                return _mock_response(200, songs_all)
            if url == srs.EVENT_TOP_API_URL and not allow_redirects:
                return _mock_response(200, {'points': [], 'users': []})
            if url == srs.BESTDORI_EVENT_TOP_URL:
                if params['interval'] == srs.SONG_RANKING_INTERVAL_MS:
                    return _mock_response(200, {'points': [], 'users': []})
                if params['interval'] == 60000:
                    return _mock_response(200, top_1m)
            return _mock_response(404, None)

        with patch.object(srs, 'EVENT_TOP_API_URL', 'http://127.0.0.1:5519/api/eventtop/data'), \
             patch.object(srs.bestdori_client, 'get_event_meta', return_value=meta), \
             patch.object(srs.bestdori_client.session, 'get', side_effect=fake_get):
            res = self.client.get('/api/events/347/song_ranking')
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body['songs'][0]['entries'][0]['uid'], 111)

    def test_force_refresh_cooldown_and_idempotent_upsert(self):
        payload1 = {
            'points': [{'time': 5000, 'uid': 777, 'value': 9100000}],
            'users': [{'uid': 777, 'name': 'OldKing'}],
        }
        payload2 = {
            'points': [{'time': 6000, 'uid': 888, 'value': 9500000}],
            'users': [{'uid': 888, 'name': 'NewKing'}],
        }
        with patch.object(srs.bestdori_client, 'get_event_meta', return_value={}), \
             patch.object(srs.bestdori_client.session, 'get', side_effect=[
                 _mock_response(200, payload1),
                 _mock_response(200, payload2),
             ]) as mock_get:
            r1 = self.client.get('/api/events/341/song_ranking?force=true')
            self.assertEqual(r1.status_code, 200)
            self.assertEqual(r1.get_json()['source'], 'backfill')
            self.assertEqual(mock_get.call_count, 1)

            # Second force within cooldown must serve DB without calling upstream
            r2 = self.client.get('/api/events/341/song_ranking?force=true')
            self.assertEqual(r2.status_code, 200)
            self.assertEqual(r2.get_json()['source'], 'db')
            self.assertEqual(mock_get.call_count, 1)

            # After cooldown expires, upsert cleanly replaces old player degree
            events_route._last_song_ranking_refresh_time.clear()
            r3 = self.client.get('/api/events/341/song_ranking?force=true')
            self.assertEqual(r3.status_code, 200)
            self.assertEqual(r3.get_json()['songs'][0]['entries'][0]['uid'], 888)
            self.assertIsNone(PlayerSongDegree.query.filter_by(event_id=341, music_id=-1, uid='777').first())
            self.assertIsNotNone(PlayerSongDegree.query.filter_by(event_id=341, music_id=-1, uid='888').first())

    def test_scheduler_backfill_rollback_in_context_and_runs_when_no_unprocessed_t10(self):
        import sys
        import types
        from models import AppState

        try:
            import scheduler
        except ModuleNotFoundError as exc:
            if exc.name not in ('pkg_resources', 'apscheduler'):
                raise
            apscheduler_mod = types.ModuleType('apscheduler')
            exec_pool_mod = types.ModuleType('apscheduler.executors.pool')
            exec_pool_mod.ThreadPoolExecutor = MagicMock
            sched_bg_mod = types.ModuleType('apscheduler.schedulers.background')
            sched_bg_mod.BackgroundScheduler = MagicMock
            stubs = {
                'apscheduler': apscheduler_mod,
                'apscheduler.executors': types.ModuleType('apscheduler.executors'),
                'apscheduler.executors.pool': exec_pool_mod,
                'apscheduler.schedulers': types.ModuleType('apscheduler.schedulers'),
                'apscheduler.schedulers.background': sched_bg_mod,
            }
            with patch.dict(sys.modules, stubs):
                import scheduler

        # 1. Exception inside backfill_ended_song_rankings must rollback inside app_context without raising RuntimeError
        self.context.pop()
        try:
            with patch.object(scheduler, 'backfill_ended_song_rankings', side_effect=RuntimeError('boom')):
                scheduler.backfill_song_rankings_job(self.app)
            # Lock must be released after failure
            self.assertTrue(scheduler._song_ranking_lock.acquire(blocking=False))
            scheduler._song_ranking_lock.release()
        finally:
            self.context.push()

        # 2. update_t10_achievements still calls backfill_song_rankings_job when no unprocessed events exist
        db.session.add(AppState(key='last_processed_t10_event_id', value='9999'))
        db.session.commit()
        with patch.object(scheduler, 'backfill_song_rankings_job') as mock_job:
            scheduler.update_t10_achievements(self.app)
        mock_job.assert_called_once_with(self.app)


if __name__ == '__main__':
    unittest.main()
