"""One-shot script to backfill chart_data_cache from existing player_score_history."""
import sys
from app import app
from models import db
from services.event_repository import backfill_chart_data_cache

if __name__ == '__main__':
    event_id = sys.argv[1] if len(sys.argv) > 1 else None
    with app.app_context():
        db.create_all()  # ensure chart_data_cache table exists
        if event_id:
            print(f"Backfilling cache for event {event_id}...")
        else:
            print("Backfilling cache for ALL events...")
        total = backfill_chart_data_cache(event_id)
        print(f"Done. Inserted {total} cache rows.")
