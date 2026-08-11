# backend/scheduler.py
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import Integer, cast
from models import db, Event, Score, PlayerDegree, AppState, PlayerScoreHistory, ChartPoint
from services.bestdori_client import client
from services.event_ingestion import backfill_event_history, parse_and_store_event_data, record_active_event_top_10
from services.event_repository import get_all_event_ids, get_event_ids_with_history, backfill_chart_data_cache
from services.heatmap import compute_heatmap_cache, heatmap_cache_covers_window
from services.monthly_ingestion import ingest_monthly_master_list, record_active_monthly_top
from services.monthly_heatmap import compute_monthly_heatmap_cache, monthly_heatmap_cache_covers_window
from services.timeutil import now_ms

KEEP_MINUTES = 30  # minutes of per-minute data to keep per ended event

logging.basicConfig(level=logging.INFO)

RANK_TO_DEGREE_ID = {
    1: 47,
    2: 48,
    3: 49,
    10: 50,
}


def discover_new_events(app):
    """
    Fetches the complete list of events from Bestdori, identifies new events,
    adds them to the database, and immediately backfills their 1-minute history.
    """
    with app.app_context():
        logging.info("Scheduler: Running discover_new_events task...")
        try:
            all_events_data = client.get_all_events()
            if not all_events_data:
                logging.error("Failed to fetch all events list from Bestdori.")
                return

            existing_event_ids = get_all_event_ids()
            logging.info(f"Found {len(existing_event_ids)} events in the local database.")

            new_event_ids = []
            for event_id in sorted(all_events_data.keys(), key=int, reverse=True):
                if event_id == '5001':
                    continue
                if event_id not in existing_event_ids:
                    new_event_ids.append(event_id)

            if not new_event_ids:
                logging.info("No new events found.")
                return

            logging.info(f"Found {len(new_event_ids)} new events. Processing and backfilling...")
            for event_id in new_event_ids:
                try:
                    logging.info(f"Processing new event: {event_id}")
                    parse_and_store_event_data(event_id)
                    logging.info(f"Successfully created base record for event {event_id}.")

                    logging.info(f"Backfilling 1-min interval data for new event {event_id}.")
                    inserted = backfill_event_history(event_id)
                    if inserted is None:
                        logging.error(f"Backfill failed for new event {event_id}.")
                    else:
                        logging.info(f"Successfully backfilled {inserted} historical points for event {event_id}.")

                    logging.info(f"Successfully processed event {event_id}. Waiting 10 seconds...")
                    time.sleep(10)
                except Exception as e:
                    logging.error(f"Failed to process new event {event_id}: {e}", exc_info=True)
                    db.session.rollback()
                    time.sleep(10)

        except Exception as e:
            logging.error(f"An error occurred in discover_new_events: {e}", exc_info=True)
            db.session.rollback()


def get_degree_id_for_rank(rank):
    if rank == 1: return RANK_TO_DEGREE_ID[1]
    if rank == 2: return RANK_TO_DEGREE_ID[2]
    if rank == 3: return RANK_TO_DEGREE_ID[3]
    if (4 <= rank <= 10) or (rank == 0):
        return RANK_TO_DEGREE_ID[10]
    return None


def update_t10_achievements(app):
    """
    Checks for newly finished events since the last run and records T10 achievements.
    """
    with app.app_context():
        logging.info("Scheduler: Running update_t10_achievements task...")
        try:
            last_processed_event_state = AppState.query.filter_by(key='last_processed_t10_event_id').first()
            if not last_processed_event_state:
                logging.info("First run for T10 achievements, creating initial state.")
                last_processed_event_state = AppState(key='last_processed_t10_event_id', value='0')
                db.session.add(last_processed_event_state)
                db.session.commit()

            last_processed_event_id = int(last_processed_event_state.value)
            current_time_ms = now_ms()

            unprocessed_events = Event.query.filter(
                Event.end_at < current_time_ms,
                cast(Event.event_id, Integer) > last_processed_event_id
            ).order_by(cast(Event.event_id, Integer).asc()).all()

            if not unprocessed_events:
                logging.info("No new finished events to process for T10 achievements.")
                return

            max_processed_id = last_processed_event_id
            for event in unprocessed_events:
                logging.info(f"Processing T10 achievements for event: {event.event_id} - {event.name}")
                t10_scores = Score.query.filter(Score.event_id == event.event_id).order_by(Score.pt.desc()).limit(10).all()

                for idx, score in enumerate(t10_scores, start=1):
                    exists = PlayerDegree.query.filter_by(uid=score.uid, event_id=score.event_id).first()
                    if not exists:
                        degree_id = get_degree_id_for_rank(idx)
                        if degree_id:
                            db.session.add(PlayerDegree(
                                uid=score.uid,
                                event_id=score.event_id,
                                rank=idx,
                                degree_id=degree_id
                            ))

                # --- Prune this event's data now that it has ended ---
                _prune_event_data(event, app)

                max_processed_id = max(max_processed_id, int(event.event_id))

            last_processed_event_state.value = str(max_processed_id)
            db.session.commit()
            logging.info(f"Successfully processed {len(unprocessed_events)} events for T10. Last processed event ID is now {max_processed_id}.")

        except Exception as e:
            logging.error(f"An error occurred in update_t10_achievements: {e}", exc_info=True)
            db.session.rollback()


def update_latest_event(app):
    """
    Fetches full data for the most recent event to ensure data is fresh.
    """
    with app.app_context():
        logging.info("Scheduler: Running update_latest_event task...")
        try:
            latest_event = Event.query.order_by(cast(Event.event_id, Integer).desc()).first()
            if latest_event and latest_event.event_id != '5001':
                logging.info(f"Updating full data for latest event: {latest_event.event_id} - {latest_event.name}")
                parse_and_store_event_data(latest_event.event_id)
        except Exception as e:
            logging.error(f"An error occurred in update_latest_event: {e}", exc_info=True)


def record_top_10_scores(app):
    """
    Records the current top 10 player scores for the active event.
    """
    with app.app_context():
        try:
            inserted = record_active_event_top_10()
            if inserted:
                logging.info(f"Recorded {inserted} new active event T10 history points.")
        except Exception as e:
            logging.error(f"An error occurred in record_top_10_scores: {e}", exc_info=True)
            db.session.rollback()


def backfill_all_events_history(app):
    """
    Runs once on startup to backfill history for any existing events that are missing it.
    """
    with app.app_context():
        logging.info("Scheduler: Running backfill_all_events_history task...")
        try:
            all_db_events = get_all_event_ids()
            events_with_history = get_event_ids_with_history()
            events_to_backfill = all_db_events - events_with_history

            if not events_to_backfill:
                logging.info("Backfill: All existing events already have score history. Nothing to do.")
                return

            logging.info(f"Backfill: Found {len(events_to_backfill)} events that need score history backfilled.")
            for event_id in sorted(list(events_to_backfill), key=int):
                if int(event_id) <= 111 or event_id == '5001':
                    continue

                try:
                    logging.info(f"Backfill: Processing event: {event_id}")
                    inserted = backfill_event_history(event_id)
                    if inserted is None:
                        logging.error(f"Backfill: Failed to fetch data for event {event_id}.")
                    else:
                        logging.info(f"Backfill: Successfully stored {inserted} historical points for event {event_id}.")
                    logging.info(f"Backfill: Finished processing event {event_id}. Waiting 10 seconds...")
                    time.sleep(10)
                except Exception as e:
                    logging.error(f"An error occurred while backfilling event {event_id}: {e}", exc_info=True)
                    db.session.rollback()
                    time.sleep(10)

        except Exception as e:
            logging.error(f"An error occurred in backfill_all_events_history: {e}", exc_info=True)
            db.session.rollback()


_heatmap_lock = threading.Lock()


def refresh_heatmap_cache(app):
    """每小时预计算并落库 top-10 玩家的 48h 热力图（读库，不再实时请求 Bestdori）。

    - 进行中的活动：每次重算（数据在变）。
    - 已结束的活动：只在缓存尚未覆盖到活动结束小时时算一次（数据已冻结）。
    - 未开始的活动：跳过。
    活动按「进行中优先、已结束按结束时间倒序」处理，保证当前活动最先有数据。
    """
    if not _heatmap_lock.acquire(blocking=False):
        logging.info("Heatmap refresh already running; skipping this tick.")
        return
    try:
        with app.app_context():
            now = now_ms()
            events = Event.query.all()
            active = [e for e in events if e.start_at <= now <= e.end_at]
            ended = [e for e in events if e.end_at and e.end_at < now]
            ended.sort(key=lambda e: e.end_at, reverse=True)

            for event in active + ended:
                eid = event.event_id
                if eid == '5001':
                    continue
                needs = event.end_at >= now or not heatmap_cache_covers_window(eid, event.end_at)
                if not needs:
                    continue
                try:
                    inserted = compute_heatmap_cache(eid)
                    if inserted:
                        logging.info(f"Heatmap cache: updated event {eid} ({inserted} players).")
                    else:
                        logging.info(f"Heatmap cache: no data for event {eid}.")
                except Exception as e:
                    logging.error(f"Heatmap cache: failed for event {eid}: {e}", exc_info=True)
                    db.session.rollback()
                time.sleep(1)  # 对 Bestdori 友好：首次回填会连续请求多个活动
    finally:
        _heatmap_lock.release()


# ---------------------------------------------------------------------------
# 月榜（月間ランキング）
# ---------------------------------------------------------------------------


def refresh_monthly_master(app):
    """每小时拉取月榜 master list，发现新的一期并落库。"""
    with app.app_context():
        logging.info("Scheduler: Running refresh_monthly_master task...")
        try:
            count = ingest_monthly_master_list()
            if count:
                logging.info(f"Monthly master: upserted {count} periods.")
            else:
                logging.info("Monthly master: no periods returned.")
        except Exception as e:
            logging.error(f"Monthly master ingest failed: {e}", exc_info=True)
            db.session.rollback()


def record_monthly_top_10(app):
    """每分钟刷新进行中的月榜 top 快照（官方 API）。"""
    with app.app_context():
        try:
            inserted = record_active_monthly_top()
            if inserted:
                logging.info(f"Recorded {inserted} new monthly top history points.")
        except Exception as e:
            logging.error(f"An error occurred in record_monthly_top_10: {e}", exc_info=True)
            db.session.rollback()


_monthly_heatmap_lock = threading.Lock()


def refresh_monthly_heatmap_cache(app):
    """每小时从 monthly_chart_points 预计算月榜 top-10 热力图并落库。

    - 进行中的月榜：每次重算（数据在变）。
    - 已结束的月榜：只在缓存尚未覆盖到结束小时时算一次（数据已冻结）。
    """
    if not _monthly_heatmap_lock.acquire(blocking=False):
        logging.info("Monthly heatmap refresh already running; skipping this tick.")
        return
    try:
        with app.app_context():
            from models import MonthlyRanking
            now = now_ms()
            periods = MonthlyRanking.query.all()
            # end_at == 0 视为后端未提供结束时间（按进行中处理，每小时重算）
            active = [p for p in periods if p.start_at <= now and (p.end_at == 0 or p.end_at >= now)]
            ended = [p for p in periods if p.end_at and p.end_at < now]
            ended.sort(key=lambda p: p.end_at, reverse=True)

            for p in active + ended:
                mid = p.monthly_id
                needs = p.end_at == 0 or p.end_at >= now or not monthly_heatmap_cache_covers_window(mid, p.end_at)
                if not needs:
                    continue
                try:
                    inserted = compute_monthly_heatmap_cache(mid)
                    if inserted:
                        logging.info(f"Monthly heatmap: updated period {mid} ({inserted} players).")
                    else:
                        logging.info(f"Monthly heatmap: no data for period {mid}.")
                except Exception as e:
                    logging.error(f"Monthly heatmap: failed for period {mid}: {e}", exc_info=True)
                    db.session.rollback()
                time.sleep(1)
    finally:
        _monthly_heatmap_lock.release()


def _prune_event_data(event, app):
    """
    After an event ends: backfill its chart_data_cache, then prune raw per-minute
    history (keep only last N minutes) and clean up legacy chart_points.
    """
    eid = event.event_id
    try:
        # 1. Backfill chart cache for this event so charts don't need raw history
        logging.info(f"Prune: Backfilling chart cache for event {eid}...")
        backfill_chart_data_cache(event_id=eid)

        # 2. Prune player_score_history: keep only last KEEP_MINUTES
        cutoff_ms = KEEP_MINUTES * 60 * 1000
        keep_threshold = event.end_at - cutoff_ms
        batch_size = 10000
        deleted = 0
        while True:
            subquery = PlayerScoreHistory.query.with_entities(
                PlayerScoreHistory.id
            ).filter(
                PlayerScoreHistory.event_id == eid,
                PlayerScoreHistory.timestamp < keep_threshold
            ).limit(batch_size).subquery()

            result = db.session.execute(
                PlayerScoreHistory.__table__.delete().where(
                    PlayerScoreHistory.id.in_(subquery)
                )
            )
            db.session.commit()
            if result.rowcount == 0:
                break
            deleted += result.rowcount
        logging.info(f"Prune: Deleted {deleted:,} history rows for event {eid} "
                      f"(kept last {KEEP_MINUTES}min).")

        # 3. Clean up legacy chart_points for this event
        cp = ChartPoint.query.filter_by(event_id=eid).delete()
        db.session.commit()
        if cp:
            logging.info(f"Prune: Deleted {cp:,} chart_points rows for event {eid}.")

    except Exception as e:
        logging.error(f"Prune: Failed for event {eid}: {e}", exc_info=True)
        db.session.rollback()


def vacuum_databases(app):
    """定期 VACUUM SQLite 库文件，回收删除行未归还的磁盘空间。

    SQLite 删除行不会自动缩小 .db 文件；活动历史被 _prune_event_data 裁剪后，
    空间要等 VACUUM 才真正释放。VACUUM 不能在任何事务内执行，故用 AUTOCOMMIT
    连接跑；运行期间会短暂锁库，所以只在「没有任何活动进行中」的日子才真正
    执行（避开逐分钟写入关键期），其余日子跳过、等下次空档。
    """
    with app.app_context():
        now = now_ms()
        active_events = Event.query.filter(
            Event.event_id != '5001',
            Event.start_at <= now,
            Event.end_at >= now,
        ).count()
        if active_events:
            logging.info(f"VACUUM skipped: {active_events} active event(s) in progress.")
            return

        for bind_name, engine in db.engines.items():
            try:
                before = os.path.getsize(engine.url.database) if engine.url.database else 0
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    conn.exec_driver_sql("VACUUM")
                after = os.path.getsize(engine.url.database) if engine.url.database else 0
                logging.info(f"VACUUM done for bind '{bind_name}': "
                             f"{before/1024/1024:.1f} MB -> {after/1024/1024:.1f} MB")
            except Exception as e:
                logging.error(f"VACUUM failed for bind '{bind_name}': {e}", exc_info=True)


def init_scheduler(app):
    """Initializes and starts the scheduler with aligned job start times."""
    executors = {
        'default': ThreadPoolExecutor(1),
        'priority': ThreadPoolExecutor(1),
        'heatmap': ThreadPoolExecutor(1),
        'maintenance': ThreadPoolExecutor(1),
    }
    scheduler = BackgroundScheduler(executors=executors, daemon=True)

    now = datetime.now()
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    startup_delay = now + timedelta(seconds=3)

    scheduler.add_job(discover_new_events, 'interval', args=[app], hours=1, start_date=next_hour, misfire_grace_time=900, executor='default', max_instances=1)
    scheduler.add_job(update_t10_achievements, 'interval', args=[app], hours=1, start_date=next_hour, misfire_grace_time=900, executor='default', max_instances=1)
    scheduler.add_job(record_top_10_scores, 'interval', args=[app], minutes=1, start_date=next_minute, misfire_grace_time=60, executor='priority', max_instances=1)
    scheduler.add_job(backfill_all_events_history, 'date', args=[app], run_date=next_minute, misfire_grace_time=300, executor='default', max_instances=1)
    scheduler.add_job(refresh_heatmap_cache, 'interval', args=[app], hours=1, start_date=next_hour, misfire_grace_time=900, executor='heatmap', max_instances=1)
    # 月榜任务
    scheduler.add_job(refresh_monthly_master, 'interval', args=[app], hours=1, start_date=next_hour, misfire_grace_time=900, executor='default', max_instances=1)
    scheduler.add_job(record_monthly_top_10, 'interval', args=[app], minutes=1, start_date=next_minute, misfire_grace_time=60, executor='priority', max_instances=1)
    scheduler.add_job(refresh_monthly_heatmap_cache, 'interval', args=[app], hours=1, start_date=next_hour, misfire_grace_time=900, executor='heatmap', max_instances=1)
    # 维护任务：每天低峰检查，仅在没有活动进行中的日子执行 VACUUM，
    # 回收被裁剪数据占用的磁盘空间（有活动时跳过，等下次空档）
    scheduler.add_job(vacuum_databases, 'cron', args=[app], hour=5, minute=12, misfire_grace_time=3600, executor='maintenance', max_instances=1)
    # Immediate startup jobs (non-blocking, run 3s after scheduler starts)
    scheduler.add_job(discover_new_events, 'date', args=[app], run_date=startup_delay, misfire_grace_time=300, executor='default', max_instances=1)
    scheduler.add_job(update_t10_achievements, 'date', args=[app], run_date=startup_delay, misfire_grace_time=300, executor='default', max_instances=1)
    scheduler.add_job(refresh_heatmap_cache, 'date', args=[app], run_date=startup_delay, misfire_grace_time=300, executor='heatmap', max_instances=1)
    scheduler.add_job(refresh_monthly_master, 'date', args=[app], run_date=startup_delay, misfire_grace_time=300, executor='default', max_instances=1)
    scheduler.add_job(refresh_monthly_heatmap_cache, 'date', args=[app], run_date=startup_delay, misfire_grace_time=300, executor='heatmap', max_instances=1)

    scheduler.start()
    logging.info("Scheduler started. Startup jobs scheduled to run immediately.")
