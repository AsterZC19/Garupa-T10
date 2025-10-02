# backend/scheduler.py
import requests
import time
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, Event
from services.fetcher import parse_and_store_event_data, BESTDORI
import logging

logging.basicConfig(level=logging.INFO)

def discover_new_events(app):
    """
    Fetches the complete list of events from Bestdori, identifies new events 
    not present in the local database, and adds them.
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

            if new_event_ids:
                logging.info(f"Found {len(new_event_ids)} new events. Fetching data...")
                # Process newest new event first
                for event_id in new_event_ids:
                    logging.info(f"Processing new event: {event_id}")
                    try:
                        # This function will create the event if it doesn't exist
                        parse_and_store_event_data(event_id)
                        logging.info(f"Successfully processed event {event_id}. Waiting 10 seconds...")
                        time.sleep(10)
                    except Exception as e:
                        logging.error(f"Failed to process new event {event_id}: {e}", exc_info=True)
                        # Wait before trying the next one to avoid cascading failures
                        time.sleep(10)
            else:
                logging.info("No new events found.")

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

def init_scheduler(app):
    """Initializes and starts the scheduler."""
    executors = {
        'default': ThreadPoolExecutor(1)
    }
    scheduler = BackgroundScheduler(executors=executors, daemon=True)
    # Discover new events every hour
    scheduler.add_job(discover_new_events, 'interval', args=[app], hours=1, misfire_grace_time=900)
    # Update the latest event every 15 minutes
    scheduler.add_job(update_latest_event, 'interval', args=[app], minutes=10, misfire_grace_time=300)
    # Process T10 achievements every hour
    scheduler.add_job(update_t10_achievements, 'interval', args=[app], hours=1, misfire_grace_time=900)
    
    scheduler.start()
    logging.info("Scheduler started with a single worker thread. Jobs scheduled.")

    # Run jobs immediately on startup in the main thread to ensure sync and avoid race conditions.
    with app.app_context():
        logging.info("Running startup jobs synchronously...")
        discover_new_events(app)
        update_latest_event(app)
        update_t10_achievements(app)
        logging.info("Startup jobs finished.")
