# backend/scheduler.py
import requests
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
            new_events_found = 0
            # Sort events by ID descending to process newest first
            sorted_event_ids = sorted(all_events_data.keys(), key=int, reverse=True)

            for event_id in sorted_event_ids:
                # Per user request, ignore the placeholder event 5001
                if event_id == '5001':
                    continue

                if event_id not in existing_event_ids:
                    new_events_found += 1
                    logging.info(f"New event found: {event_id}. Adding to database.")
                    event_data = all_events_data[event_id]
                    
                    # 4. Create and save the new event
                    name = event_data.get('eventName', [''])[0]
                    event_type = event_data.get('eventType', '')
                    start_at = event_data.get('startAt', ['0'])[0]
                    end_at = event_data.get('endAt', ['0'])[0]

                    new_event = Event(
                        event_id=str(event_id),
                        name=name,
                        event_type=event_type,
                        start_at=int(start_at) if start_at else 0,
                        end_at=int(end_at) if end_at else 0
                    )
                    db.session.add(new_event)
            
            if new_events_found > 0:
                db.session.commit()
                logging.info(f"Successfully added {new_events_found} new events to the database.")
            else:
                logging.info("No new events found.")

        except Exception as e:
            logging.error(f"An error occurred in discover_new_events: {e}", exc_info=True)
            db.session.rollback()

from sqlalchemy import cast, Integer

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

def init_scheduler(app):
    """Initializes and starts the scheduler."""
    scheduler = BackgroundScheduler(daemon=True)
    # Discover new events every hour
    scheduler.add_job(discover_new_events, 'interval', args=[app], hours=1, misfire_grace_time=900)
    # Update the latest event every 15 minutes
    scheduler.add_job(update_latest_event, 'interval', args=[app], minutes=5, misfire_grace_time=300)
    
    scheduler.start()
    logging.info("Scheduler started. Jobs scheduled.")

    # Run jobs immediately on startup in a separate thread to not block app start
    import threading
    def run_startup_jobs():
        with app.app_context():
            logging.info("Running startup jobs...")
            discover_new_events(app)
            update_latest_event(app)
            logging.info("Startup jobs finished.")
    
    threading.Thread(target=run_startup_jobs).start()
