"""Offline regressions: python -m unittest discover -s backend -p test_ranking_snapshot.py."""
import unittest
from unittest.mock import patch

from flask import Flask

from models import db, Event, Score, MonthlyScore, PlayerScoreHistory, MonthlyChartPoint
from services import event_ingestion, monthly_ingestion
from services.ranking_snapshot import latest_snapshot_by_uid


class RankingSnapshotTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_BINDS'] = {'degrees': 'sqlite:///:memory:'}
        db.init_app(app)
        self.context = app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(Event(event_id='345', start_at=0, end_at=999999))
        db.session.commit()
        event_ingestion._last_stored_ts.clear()
        # The removed player's score remains in history and metadata. The two
        # polls share a minute: membership must be selected before bucketing.
        self.snapshot = {
            'users': [
                {'uid': 'removed', 'name': '旧榜首', 'current_pt': 9999},
                {'uid': 'stopped', 'name': '正常停分玩家', 'rank': 400},
                {'uid': 'new', 'name': '递补玩家', 'rank': 300},
            ],
            'points': [
                {'uid': 'new', 'time': 121000, 'value': 400},
                {'uid': 'removed', 'time': 120000, 'value': 9999},
                {'uid': 'stopped', 'time': 120000, 'value': 500},
                {'uid': 'stopped', 'time': 121000, 'value': 500},
            ],
        }

    def tearDown(self):
        db.session.remove()
        for engine in db.engines.values():
            engine.dispose()
        self.context.pop()
        event_ingestion._last_stored_ts.clear()

    def test_snapshot_is_order_independent_and_supports_timestamp_alias(self):
        points = self.snapshot['points']
        expected = latest_snapshot_by_uid(points)
        self.assertEqual(set(expected), {'stopped', 'new'})
        self.assertEqual(latest_snapshot_by_uid(list(reversed(points))), expected)
        self.assertEqual(latest_snapshot_by_uid([
            {'uid': 'zero', 'timestamp': 122000, 'value': 0}, *points
        ]), {'zero': {'uid': 'zero', 'timestamp': 122000, 'pt': 0}})

    def test_event_initial_and_periodic_refresh_replace_stale_members(self):
        for refresh in (False, True):
            with self.subTest(refresh=refresh):
                db.session.add(Score(event_id='345', uid='removed', pt=9999))
                db.session.commit()
                with patch.object(event_ingestion.client, 'get_event_top_data', return_value=self.snapshot):
                    if refresh:
                        event_ingestion.refresh_event_top_data('345')
                    else:
                        event_ingestion.compute_speeds_and_store('345', self.snapshot)
                scores = Score.query.order_by(Score.rank).all()
                self.assertEqual([(s.uid, s.pt, s.rank) for s in scores], [
                    ('stopped', 500, 1), ('new', 400, 2)])
                self.assertEqual({s.updated_at for s in scores}, {121000})
        # Historical data is still available for charts and statistics.
        self.assertIsNotNone(PlayerScoreHistory.query.filter_by(uid='removed').first())

    def test_monthly_refresh_and_backfill_replace_stale_members(self):
        for ingest in (monthly_ingestion.refresh_monthly_top, monthly_ingestion.backfill_monthly_history):
            with self.subTest(ingest=ingest.__name__):
                db.session.add(MonthlyScore(monthly_id=25, uid='removed', pt=9999))
                db.session.commit()
                with patch.object(monthly_ingestion.tracker_client, 'get_monthly_top', return_value=self.snapshot):
                    ingest(25)
                scores = MonthlyScore.query.order_by(MonthlyScore.rank).all()
                self.assertEqual([(s.uid, s.pt, s.rank) for s in scores], [
                    ('stopped', 500, 1), ('new', 400, 2)])
                self.assertIsNotNone(MonthlyChartPoint.query.filter_by(uid='removed').first())

    def test_missing_profiles_do_not_change_membership(self):
        rows = event_ingestion.build_score_rows('345', self.snapshot['points'], [])
        self.assertEqual([r['uid'] for r in rows], ['stopped', 'new'])
        self.assertEqual(rows[0]['name'], 'stopped')
        rows = monthly_ingestion._latest_scores_from_snapshot(25, self.snapshot['points'], [])
        self.assertEqual([r['uid'] for r in rows], ['stopped', 'new'])

    def test_empty_or_failed_fetch_keeps_existing_ranking(self):
        db.session.add(Score(event_id='345', uid='existing', pt=10))
        db.session.add(MonthlyScore(monthly_id=25, uid='existing', pt=10))
        db.session.commit()
        for payload in (None, {'points': [], 'users': []}):
            with patch.object(event_ingestion.client, 'get_event_top_data', return_value=payload):
                event_ingestion.compute_speeds_and_store('345', payload)
                event_ingestion.refresh_event_top_data('345')
        with patch.object(monthly_ingestion.tracker_client, 'get_monthly_top', return_value={'points': [], 'users': []}):
            monthly_ingestion.refresh_monthly_top(25)
            monthly_ingestion.backfill_monthly_history(25)
        with patch.object(monthly_ingestion.tracker_client, 'get_monthly_top', side_effect=monthly_ingestion.TrackerError('offline')):
            monthly_ingestion.refresh_monthly_top(25)
            monthly_ingestion.backfill_monthly_history(25)
        self.assertEqual([s.uid for s in Score.query.all()], ['existing'])
        self.assertEqual([s.uid for s in MonthlyScore.query.all()], ['existing'])


if __name__ == '__main__':
    unittest.main()
