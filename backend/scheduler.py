# backend/scheduler.py
import requests
import time
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, Event, PlayerDegree, AppState, PlayerScoreHistory
from services.fetcher import parse_and_store_event_data, BESTDORI
import logging
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime, timedelta
from collections import defaultdict

logging.basicConfig(level=logging.INFO)

def discover_new_events(app):
    """
    Fetches the complete list of events from Bestdori, identifies new events,
    adds them to the database, and immediately backfills their entire 1-minute
    interval score history.
    """
    with app.app_context():
        logging.info("Scheduler: Running discover_new_events task...")
        try:
            # 1. Fetch all events from Bestdori's master list
            all_events_url = f"{BESTDORI}/api/events/all.5.json"
            response = requests.get(all_events_url, timeout=15)
            if response.status_code != 200:
                logging.error(f"Failed to fetch all events list from Bestdori. Status: {response.status_code}")
                return
            
            all_events_data = response.json()

            # 2. Get all existing event IDs from the local database
            existing_event_ids = {str(e.event_id) for e in Event.query.with_entities(Event.event_id).all()}
            logging.info(f"Found {len(existing_event_ids)} events in the local database.")

            # 3. Compare and find new events
            new_event_ids = []
            sorted_event_ids = sorted(all_events_data.keys(), key=int, reverse=True)

            for event_id in sorted_event_ids:
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
                    # Step A: Create the base event record so other tasks can see it
                    parse_and_store_event_data(event_id)
                    logging.info(f"Successfully created base record for event {event_id}.")

                    # Step B: Backfill the entire 1-minute history for the new event
                    logging.info(f"Backfilling 1-min interval data for new event {event_id}.")
                    url = f"https://bestdori.com/api/eventtop/data?server=jp&event={event_id}&mid=0&interval=60000"
                    response = requests.get(url, timeout=60)
                    if response.status_code != 200:
                        logging.error(f"Backfill failed for new event {event_id}. Status: {response.status_code}")
                        # Skip to next event, but wait to avoid hammering API
                        time.sleep(10)
                        continue

                    data = response.json()
                    points_data = data.get('points', [])
                    users_data = data.get('users', [])

                    if not points_data:
                        logging.info(f"No points data to backfill for new event {event_id}.")
                        time.sleep(10) # Still wait before next event
                        continue
                    
                    name_map = {str(u.get('uid')): u.get('name', '') for u in users_data}
                    
                    history_records_to_add = []
                    for p in points_data:
                        uid = str(p.get('uid'))
                        name_from_meta = name_map.get(uid)
                        final_name = name_from_meta if name_from_meta and name_from_meta.strip() else uid
                        
                        history_records_to_add.append(
                            PlayerScoreHistory(
                                event_id=event_id,
                                uid=uid,
                                name=final_name,
                                pt=p.get('value'),
                                timestamp=p.get('time')
                            )
                        )
                    
                    if history_records_to_add:
                        # Use a transaction to add all records for this event
                        db.session.bulk_save_objects(history_records_to_add)
                        db.session.commit()
                        logging.info(f"Successfully backfilled {len(history_records_to_add)} historical points for event {event_id}.")
                    else:
                        logging.info(f"No new historical points to backfill for event {event_id}.")

                    logging.info(f"Successfully processed and backfilled event {event_id}. Waiting 10 seconds...")
                    time.sleep(10)

                except Exception as e:
                    logging.error(f"Failed to process new event {event_id}: {e}", exc_info=True)
                    db.session.rollback()
                    # Wait before trying the next one to avoid cascading failures
                    time.sleep(10)

        except Exception as e:
            logging.error(f"An error occurred in discover_new_events: {e}", exc_info=True)
            db.session.rollback()

from sqlalchemy import cast, Integer

# --- New T10 Achievement Processing Task ---
from models import Score, PlayerDegree, AppState

RANK_TO_DEGREE_ID = {
    1: 47,  # T1
    2: 48,  # T2
    3: 49,  # T3
    10: 50, # T4-T10
}

def get_degree_id_for_rank(rank):
    if rank == 1: return RANK_TO_DEGREE_ID[1]
    if rank == 2: return RANK_TO_DEGREE_ID[2]
    if rank == 3: return RANK_TO_DEGREE_ID[3]
    if (4 <= rank <= 10) or (rank == 0): # Treat rank 0 as a T10 finish
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
            current_time_ms = int(time.time() * 1000)

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

                # 🔹 按 pt 降序获取前 10
                t10_scores = Score.query.filter(
                    Score.event_id == event.event_id
                ).order_by(Score.pt.desc()).limit(10).all()

                # 重新给他们排 rank
                for idx, score in enumerate(t10_scores, start=1):
                    exists = PlayerDegree.query.filter_by(uid=score.uid, event_id=score.event_id).first()
                    if not exists:
                        degree_id = get_degree_id_for_rank(idx)
                        if degree_id:
                            new_achievement = PlayerDegree(
                                uid=score.uid,
                                event_id=score.event_id,
                                rank=idx,   # 🔹 用真实的 pt 排名
                                degree_id=degree_id
                            )
                            db.session.add(new_achievement)

                max_processed_id = max(max_processed_id, int(event.event_id))

            last_processed_event_state.value = str(max_processed_id)
            db.session.commit()
            logging.info(f"Successfully processed {len(unprocessed_events)} events for T10. Last processed event ID is now {max_processed_id}.")

        except Exception as e:
            logging.error(f"An error occurred in update_t10_achievements: {e}", exc_info=True)
            db.session.rollback()


# --- End of New Task ---

def update_latest_event(app):
    """
    Fetches full data for the most recent event to ensure data is fresh.
    """
    with app.app_context():
        logging.info(f"Scheduler: Running update_latest_event task...")
        try:
            # Cast event_id to Integer for correct numerical sorting and get the latest one
            latest_event = Event.query.order_by(cast(Event.event_id, Integer).desc()).first()
            if latest_event:
                # Per user request, ignore the placeholder event 5001
                if latest_event.event_id == '5001':
                    return
                logging.info(f"Updating full data for latest event: {latest_event.event_id} - {latest_event.name}")
                parse_and_store_event_data(latest_event.event_id)
        except Exception as e:
            logging.error(f"An error occurred in update_latest_event: {e}", exc_info=True)

from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime, timedelta

# --- New T10 Score Recording Task ---
from models import PlayerScoreHistory

def record_top_10_scores(app):
    """
    Records the current top 10 player scores for the active event.
    """
    with app.app_context():
        try:
            current_time_ms = int(time.time() * 1000)
            
            # Find the currently active event
            active_event = Event.query.filter(
                Event.start_at <= current_time_ms,
                Event.end_at >= current_time_ms
            ).order_by(Event.start_at.desc()).first()

            if not active_event:
                # logging.info("No active event found for T10 score recording.")
                return

            event_id = active_event.event_id
            # logging.info(f"Recording T10 scores for active event: {event_id}")

            # Fetch T10 data from Bestdori API using the established endpoint
            url = f"https://bestdori.com/api/eventtop/data?server=jp&event={event_id}&mid=0&interval=900000"
            response = requests.get(url, timeout=15)

            if response.status_code != 200:
                logging.error(f"Failed to fetch T10 data for event {event_id}. Status: {response.status_code}")
                return

            data = response.json()
            points_data = data.get('points', [])
            users_data = data.get('users', [])

            if not points_data:
                logging.warning(f"Points data for event {event_id} was empty.")
                return

            # Step 1: Derive definitive ranking from the 'points' array
            latest_scores = {}
            for p in points_data:
                uid = str(p.get('uid'))
                timestamp = p.get('time')
                pt_value = p.get('value')
                if uid not in latest_scores or timestamp > latest_scores[uid]['timestamp']:
                    latest_scores[uid] = {'uid': uid, 'pt': pt_value, 'timestamp': timestamp}
            
            definitive_ranking = sorted(latest_scores.values(), key=lambda x: x['pt'], reverse=True)

            # Step 2: Create a lookup map for user metadata
            user_meta_map = {str(u.get('uid')): u for u in users_data}

            # Step 3: Combine and save the top 10
            t10_ranking = definitive_ranking[:10]
            
            # --- Update Score Table (Snapshot) ---
            score_records_to_upsert = []
            for i, ranking_info in enumerate(t10_ranking):
                uid = ranking_info['uid']
                meta = user_meta_map.get(uid, {})
                name_from_meta = meta.get('name')
                final_name = name_from_meta if name_from_meta and name_from_meta.strip() else uid
                ranking_info['final_name'] = final_name # Store final_name in ranking_info

                score_records_to_upsert.append({
                    'event_id': event_id, 'uid': uid, 'name': final_name,
                    'pt': ranking_info['pt'], 'rank': i + 1, 'signature': meta.get('introduction', ''),
                    'updated_at': ranking_info['timestamp'] # Use API timestamp
                })
            
            if score_records_to_upsert:
                db.session.query(Score).filter(Score.event_id == event_id).delete(synchronize_session=False)
                db.session.bulk_insert_mappings(Score, score_records_to_upsert)

            # --- Update PlayerScoreHistory Table (Append Only) ---
            # Check which of the latest points from the API are already in our history table
            latest_points_tuples = [(str(p['uid']), p['timestamp']) for p in t10_ranking]
            
            existing_points = db.session.query(PlayerScoreHistory.uid, PlayerScoreHistory.timestamp).filter(
                PlayerScoreHistory.event_id == event_id,
                db.tuple_(PlayerScoreHistory.uid, PlayerScoreHistory.timestamp).in_(latest_points_tuples)
            ).all()
            existing_set = set(existing_points)

            history_records_to_add = []
            for ranking_info in t10_ranking:
                uid = ranking_info['uid']
                timestamp = ranking_info['timestamp']
                if (uid, timestamp) not in existing_set:
                    history_records_to_add.append(
                        PlayerScoreHistory(
                            event_id=event_id,
                            uid=uid,
                            name=ranking_info['final_name'], # Use stored final_name
                            pt=ranking_info['pt'],
                            timestamp=timestamp
                        )
                    )
            if history_records_to_add:
                db.session.bulk_save_objects(history_records_to_add)

            db.session.commit()
            # logging.info(f"Successfully recorded and updated {len(history_records)} T10 scores for event {event_id}.")

        except Exception as e:
            logging.error(f"An error occurred in record_top_10_scores: {e}", exc_info=True)
            db.session.rollback()

# --- End of New Task ---

def backfill_all_events_history(app):
    """
    Runs once on startup to backfill history for any existing events that
    are missing it in the PlayerScoreHistory table.
    """
    with app.app_context():
        logging.info("Scheduler: Running backfill_all_events_history task...")
        try:
            # 1. Get all event IDs from the main Event table
            all_db_events = {str(e.event_id) for e in Event.query.with_entities(Event.event_id).all()}
            
            # 2. Get all event IDs that already have some data in the history table
            events_with_history = {str(h.event_id) for h in PlayerScoreHistory.query.with_entities(PlayerScoreHistory.event_id).distinct().all()}

            # 3. Find events that need backfilling
            events_to_backfill = all_db_events - events_with_history
            
            if not events_to_backfill:
                logging.info("Backfill: All existing events already have score history. Nothing to do.")
                return

            logging.info(f"Backfill: Found {len(events_to_backfill)} events that need score history backfilled.")

            # Sort to process them in a predictable order (e.g., oldest to newest)
            sorted_events_to_backfill = sorted(list(events_to_backfill), key=int)

            for event_id in sorted_events_to_backfill:
                # Per user request, skip events up to 111 as they have no data
                if int(event_id) <= 111:
                    continue

                if event_id == '5001':
                    continue
                
                try:
                    logging.info(f"Backfill: Processing event: {event_id}")
                    
                    # Fetch the complete 1-minute interval history
                    url = f"https://bestdori.com/api/eventtop/data?server=jp&event={event_id}&mid=0&interval=60000"
                    response = requests.get(url, timeout=60)
                    if response.status_code != 200:
                        logging.error(f"Backfill: Failed to fetch data for event {event_id}. Status: {response.status_code}")
                        time.sleep(10) # Wait before next
                        continue

                    data = response.json()
                    points_data = data.get('points', [])
                    users_data = data.get('users', [])

                    if not points_data:
                        logging.info(f"Backfill: No points data found for event {event_id}.")
                        time.sleep(10) # Wait before next
                        continue

                    # Create a map for user names for efficiency
                    name_map = {str(u.get('uid')): u.get('name', '') for u in users_data}

                    history_records_to_add = []
                    for p in points_data:
                        uid = str(p.get('uid'))
                        name_from_meta = name_map.get(uid)
                        final_name = name_from_meta if name_from_meta and name_from_meta.strip() else uid
                        
                        history_records_to_add.append(
                            PlayerScoreHistory(
                                event_id=event_id,
                                uid=uid,
                                name=final_name,
                                pt=p.get('value'),
                                timestamp=p.get('time')
                            )
                        )

                    if history_records_to_add:
                        db.session.bulk_save_objects(history_records_to_add)
                        db.session.commit()
                        logging.info(f"Backfill: Successfully stored {len(history_records_to_add)} historical points for event {event_id}.")
                    else:
                        logging.info(f"Backfill: No new historical points to store for event {event_id}.")

                    logging.info(f"Backfill: Finished processing event {event_id}. Waiting 10 seconds...")
                    time.sleep(10)

                except Exception as e:
                    logging.error(f"An error occurred while backfilling event {event_id}: {e}", exc_info=True)
                    db.session.rollback()
                    time.sleep(10) # Wait before trying the next one

        except Exception as e:
            logging.error(f"An error occurred in backfill_all_events_history: {e}", exc_info=True)
            db.session.rollback()

def init_scheduler(app):
    """Initializes and starts the scheduler with aligned job start times."""
    executors = {
        'default': ThreadPoolExecutor(1),  # Pool for heavy, long-running jobs
        'priority': ThreadPoolExecutor(3) # Dedicated pool for time-sensitive jobs
    }
    scheduler = BackgroundScheduler(executors=executors, daemon=True)
    
    now = datetime.now()
    # Align start times to the top of the next minute/hour
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    # Assign heavy jobs to the 'default' executor
    scheduler.add_job(discover_new_events, 'interval', args=[app], hours=1, start_date=next_hour, misfire_grace_time=900, executor='default', max_instances=1)
    
    # Assign heavy jobs to the 'default' executor
    scheduler.add_job(update_t10_achievements, 'interval', args=[app], hours=1, start_date=next_hour, misfire_grace_time=900, executor='default', max_instances=1)
    
    # Assign the time-sensitive job to the 'priority' executor
    scheduler.add_job(record_top_10_scores, 'interval', args=[app], minutes=1, start_date=next_minute, misfire_grace_time=60, executor='priority', max_instances=1)
    
    scheduler.start()
    logging.info(f"Scheduler started. Jobs aligned to start at the top of the minute/hour.")

    # Run jobs immediately on startup in the main thread to ensure sync and avoid race conditions.
    with app.app_context():
        logging.info("Running startup jobs synchronously...")
        discover_new_events(app)
        backfill_all_events_history(app) # New backfill task
        update_t10_achievements(app)
        logging.info("Startup jobs finished.")
