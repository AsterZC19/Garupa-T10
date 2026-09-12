"""Offline regression tests: python -m unittest discover -s backend -p test_player_name_history.py."""
import multiprocessing
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from models import db, PlayerNameHistory
from routes.player import player_bp
from services.player_name_history import record_names, get_name_history, init_name_history
from services import player_query_service as query
from services import event_ingestion, monthly_ingestion


def initialize_in_process(database_uri, barrier):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    db.init_app(app)
    with app.app_context():
        try:
            barrier.wait(timeout=15)
            init_name_history()
        finally:
            db.engine.dispose()


class NameHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + self.directory.name + '/test.db'
        self.app.config['SQLALCHEMY_BINDS'] = {'degrees': 'sqlite:///:memory:'}
        db.init_app(self.app)
        self.app.register_blueprint(player_bp, url_prefix='/api/player')
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        query.player_cache.clear()

    def tearDown(self):
        db.session.remove()
        for engine in db.engines.values():
            engine.dispose()
        self.context.pop()
        self.directory.cleanup()

    def test_concurrent_startup_and_restart_preserve_history(self):
        PlayerNameHistory.__table__.drop(db.engine)
        context = multiprocessing.get_context('spawn')  # Windows process semantics
        for existing_table in (False, True):
            barrier = context.Barrier(2)
            processes = [
                context.Process(target=initialize_in_process, args=(
                    self.app.config['SQLALCHEMY_DATABASE_URI'], barrier))
                for _ in range(2)
            ]
            try:
                for process in processes:
                    process.start()
                for process in processes:
                    process.join(timeout=30)
                    self.assertEqual(process.exitcode, 0)
            finally:
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                        process.join()
            if not existing_table:
                record_names([{'uid': 123, 'name': '保留名字'}], 100)
            self.assertEqual(get_name_history(123), [
                {'name': '保留名字', 'last_seen': 100}])

    def test_unique_names_latest_observation_and_persistence(self):
        for name, timestamp in [('旧名', 100), ('新名', 200), ('旧名', 300), ('旧名', 50)]:
            record_names([{'uid': '00123', 'name': name}], timestamp)
        record_names([{'uid': 123, 'name': '  '}, {'uid': None, 'name': 'bad'}], 400)
        record_names([{'uid': 456, 'name': '旧名'}], 500)
        db.session.remove()
        db.engine.dispose()
        self.assertEqual(get_name_history(123), [
            {'name': '旧名', 'last_seen': 300}, {'name': '新名', 'last_seen': 200}])

    def test_query_records_and_cache_only_reads_history(self):
        with patch.object(query.client, 'get_player_profile', return_value={'data': {'profile': {'userName': '名字'}}}) as profile, \
             patch.object(query.client, 'get_player_cheer', return_value={'data': []}), \
             patch.object(query, 'extract_area_item_levels', return_value=[]):
            first = self.app.test_client().get('/api/player/123').get_json()
            self.assertEqual(first['name_history'][0]['name'], '名字')
            record_names([{'uid': 123, 'name': '榜单新名'}], first['name_history'][0]['last_seen'] + 1)
            second = self.app.test_client().get('/api/player/123').get_json()
            self.assertEqual(profile.call_count, 1)
            self.assertEqual(second['name_history'][1], first['name_history'][0])
            self.assertEqual(second['name_history'][0]['name'], '榜单新名')
            query.player_cache.clear()
            profile.return_value = {'data': {'profile': {'user': {'name': '又改名'}}}}
            third = self.app.test_client().get('/api/player/123').get_json()
            self.assertEqual({r['name'] for r in third['name_history']}, {'名字', '榜单新名', '又改名'})

    def test_failed_query_does_not_record(self):
        with patch.object(query.client, 'get_player_profile', return_value=None), \
             patch.object(query.client, 'get_player_cheer', return_value=None):
            self.assertEqual(self.app.test_client().get('/api/player/123').status_code, 404)
            self.assertEqual(get_name_history(123), [])

    def test_event_ingestion_paths_record_without_new_points(self):
        top = {'users': [{'uid': '123', 'name': '活动名'}], 'points': []}
        with patch.object(event_ingestion.client, 'get_event_top_data', return_value=top), \
             patch.object(event_ingestion.repo, 'get_event', return_value=None), \
             patch.object(event_ingestion.repo, 'append_player_score_history_if_missing', return_value=0):
            event_ingestion.compute_speeds_and_store('1', top)
            self.assertEqual(get_name_history(123)[0]['name'], '活动名')
            top['users'][0]['name'] = '刷新名'
            event_ingestion.refresh_event_top_data('1')
            top['users'][0]['name'] = '回填名'
            event_ingestion.backfill_event_history('1')
            self.assertEqual({r['name'] for r in get_name_history(123)}, {'活动名', '刷新名', '回填名'})

    def test_monthly_ingestion_paths_record_without_new_points(self):
        top = {'users': [{'uid': '123', 'name': '月榜名'}], 'points': []}
        with patch.object(monthly_ingestion.tracker_client, 'get_monthly_top', return_value=top):
            monthly_ingestion.refresh_monthly_top(1)
            top['users'][0]['name'] = '月榜回填名'
            monthly_ingestion.backfill_monthly_history(1)
            self.assertEqual({r['name'] for r in get_name_history(123)}, {'月榜名', '月榜回填名'})


if __name__ == '__main__':
    unittest.main()
