"""One-shot script to precompute & store heatmap caches (top-10, 48h) for events.

Mirrors backfill_chart_cache.py. The scheduler also does this hourly in the
background (services.heatmap), but running this script pre-seeds everything at
deploy time instead of waiting.

Usage:
  python backfill_heatmap_cache.py                  # all events
  python backfill_heatmap_cache.py 338              # single event
  python backfill_heatmap_cache.py 337,338,339      # several events
"""
import sys
import time
from app import app
from models import db, Event
from services import event_repository as repo
from services.heatmap import compute_heatmap_cache


def main():
    args = sys.argv[1:]
    with app.app_context():
        db.create_all()  # ensure event_heatmap_cache table exists

        if args:
            targets = []
            for arg in args:
                targets.extend(e.strip() for e in arg.split(',') if e.strip())
        else:
            targets = [str(e.event_id) for e in Event.query.order_by(
                Event.end_at.desc()
            ).all()]

        print(f"Backfilling heatmap cache for {len(targets)} event(s)...")
        done = 0
        for eid in targets:
            if eid == '5001':
                continue
            t0 = time.time()
            try:
                inserted = compute_heatmap_cache(eid)
                status = f"stored {inserted} players" if inserted else "no data"
                print(f"  {eid}: {status} ({time.time()-t0:.1f}s)")
                if inserted:
                    done += 1
            except Exception as e:
                print(f"  {eid}: FAILED ({e})")
            time.sleep(1)

        print(f"Done. Heatmap cache ready for {done} of {len(targets)} events.")


if __name__ == '__main__':
    main()
