"""
One-shot database pruning script.

Operations (in order):
1. Ensure chart_data_cache table exists and backfill from player_score_history
2. Prune player_score_history — keep only last KEEP_MINUTES of per-minute data per ended event
3. Clean up chart_points legacy data for ended events
4. Report size before/after and recommend VACUUM

Usage:
  python prune_database.py                  # default: keep last 30 min
  python prune_database.py --keep-minutes 60
  python prune_database.py --dry-run        # show what would be deleted without doing it
"""

import argparse
import os
import sys
import time

from app import app
from models import db, Event, PlayerScoreHistory, ChartPoint, ChartDataCache
from services.event_repository import backfill_chart_data_cache, get_event_ids_with_history
from services.timeutil import now_ms


def get_db_size_mb():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')
    if os.path.exists(db_path):
        return os.path.getsize(db_path) / (1024 * 1024)
    return 0


def count_rows(table):
    return db.session.query(table).count()


def step_backfill_cache():
    """Ensure chart_data_cache exists and is populated for all events with history."""
    print("\n" + "=" * 60)
    print("STEP 1: Backfill chart_data_cache")
    print("=" * 60)

    # Ensure table exists
    db.create_all()
    print("Ensured chart_data_cache table exists.")

    events_with_history = sorted(get_event_ids_with_history())
    print(f"Found {len(events_with_history)} events with player_score_history data.")

    total = backfill_chart_data_cache()
    print(f"Backfill complete. Inserted {total:,} cache rows total.")
    return total


def step_prune_history(keep_minutes=30, dry_run=False):
    """Prune player_score_history: keep only last keep_minutes of per-minute data per ended event."""
    print("\n" + "=" * 60)
    print("STEP 2: Prune player_score_history")
    print("=" * 60)

    now = now_ms()
    cutoff_ms = keep_minutes * 60 * 1000

    # Find ended events that have history data
    ended_events = Event.query.filter(
        Event.end_at > 0,
        Event.end_at < now - 24 * 3600 * 1000  # ended more than 24h ago
    ).order_by(Event.event_id.asc()).all()

    if not ended_events:
        print("No ended events to prune.")
        return 0

    print(f"Found {len(ended_events)} ended events (ended >24h ago).")
    print(f"Keeping last {keep_minutes} minutes of per-minute data per event.")

    total_deleted = 0
    for event in ended_events:
        keep_threshold = event.end_at - cutoff_ms

        # Count rows to delete
        count_query = PlayerScoreHistory.query.filter(
            PlayerScoreHistory.event_id == event.event_id,
            PlayerScoreHistory.timestamp < keep_threshold
        )
        to_delete = count_query.count()

        if to_delete == 0:
            continue

        keep_count = PlayerScoreHistory.query.filter(
            PlayerScoreHistory.event_id == event.event_id,
            PlayerScoreHistory.timestamp >= keep_threshold
        ).count()

        if dry_run:
            print(f"  [DRY RUN] Event {event.event_id}: would delete {to_delete:,} rows "
                  f"(keep {keep_count:,} rows — last {keep_minutes}min)")
            total_deleted += to_delete
            continue

        # Batch delete in chunks
        deleted = 0
        batch_size = 10000
        while True:
            subquery = PlayerScoreHistory.query.with_entities(
                PlayerScoreHistory.id
            ).filter(
                PlayerScoreHistory.event_id == event.event_id,
                PlayerScoreHistory.timestamp < keep_threshold
            ).limit(batch_size).subquery()

            result = db.session.execute(
                PlayerScoreHistory.__table__.delete().where(
                    PlayerScoreHistory.id.in_(subquery)
                )
            )
            db.session.commit()

            batch_deleted = result.rowcount
            if batch_deleted == 0:
                break
            deleted += batch_deleted

        print(f"  Event {event.event_id}: deleted {deleted:,} rows "
              f"(kept {keep_count:,} rows — last {keep_minutes}min)")
        total_deleted += deleted

    if dry_run:
        print(f"\n[DRY RUN] Would delete {total_deleted:,} rows total from player_score_history.")
    else:
        print(f"\nDeleted {total_deleted:,} rows total from player_score_history.")
    return total_deleted


def step_cleanup_chart_points(dry_run=False):
    """Clean up chart_points for ended events. Keep only active event data."""
    print("\n" + "=" * 60)
    print("STEP 3: Clean up chart_points (legacy table)")
    print("=" * 60)

    now = now_ms()

    ended_events = Event.query.filter(
        Event.end_at > 0,
        Event.end_at < now - 24 * 3600 * 1000
    ).all()

    if not ended_events:
        print("No ended events to clean up.")
        return 0

    ended_event_ids = [e.event_id for e in ended_events]
    to_delete = ChartPoint.query.filter(
        ChartPoint.event_id.in_(ended_event_ids)
    ).count()

    if to_delete == 0:
        print("No chart_points to clean up for ended events.")
        return 0

    if dry_run:
        print(f"[DRY RUN] Would delete {to_delete:,} rows from chart_points "
              f"({len(ended_event_ids)} ended events).")
        return to_delete

    # Batch delete by event
    deleted = 0
    for eid in ended_event_ids:
        result = ChartPoint.query.filter_by(event_id=eid).delete()
        deleted += result
    db.session.commit()

    print(f"Deleted {deleted:,} rows from chart_points ({len(ended_event_ids)} ended events).")
    return deleted


def print_summary(before_size, keep_minutes, dry_run=False, history_deleted=0, cp_deleted=0):
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"\nDatabase size before: {before_size:.1f} MB")
    print(f"Keep threshold: last {keep_minutes} minutes per ended event")

    history_count = count_rows(PlayerScoreHistory)
    chart_points_count = count_rows(ChartPoint)
    events_count = count_rows(Event)
    scores_count = count_rows(db.Model.registry._class_registry['Score'])
    cache_count = count_rows(ChartDataCache)

    if dry_run:
        print(f"\nRow counts (current, no changes made):")
        print(f"  events:              {events_count:,}")
        print(f"  scores:              {scores_count:,}")
        print(f"  chart_data_cache:    {cache_count:,}")
        print(f"  chart_points:        {chart_points_count:,}  (would delete ~{cp_deleted:,})")
        print(f"  player_score_history: {history_count:,}  (would delete ~{history_deleted:,})")
        print(f"\nProjected player_score_history after pruning: ~{history_count - history_deleted:,}")
        if history_count > 0:
            reduction_pct = history_deleted / history_count * 100
            print(f"Projected reduction: {reduction_pct:.1f}% of history rows")
    else:
        print(f"\nRow counts after pruning:")
        print(f"  events:              {events_count:,}")
        print(f"  scores:              {scores_count:,}")
        print(f"  chart_data_cache:    {cache_count:,}")
        print(f"  chart_points:        {chart_points_count:,}")
        print(f"  player_score_history: {history_count:,}")

    final_size = get_db_size_mb()
    print(f"\nDatabase size now: {final_size:.1f} MB")
    if not dry_run:
        print(f"(Space not reclaimed until VACUUM. Run: sqlite3 data.db \"VACUUM\")")

    if not dry_run and final_size > 100:
        print("\n⚠️  To reclaim disk space, run:")
        print("    sqlite3 data.db \"VACUUM\"")
        print("  This may take several minutes and will briefly lock the database.")


def main():
    parser = argparse.ArgumentParser(description="Prune database historical data")
    parser.add_argument('--keep-minutes', type=int, default=30,
                        help='Minutes of per-minute data to keep per ended event (default: 30)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deleted without actually deleting')
    parser.add_argument('--skip-backfill', action='store_true',
                        help='Skip chart_data_cache backfill (use if already done)')
    args = parser.parse_args()

    before_size = get_db_size_mb()
    print(f"Database size before pruning: {before_size:.1f} MB")
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE'}")
    print(f"Keep minutes per ended event: {args.keep_minutes}")

    with app.app_context():
        # Step 1: Backfill cache — only in live mode (backfill writes data)
        cache_rows = count_rows(ChartDataCache)
        if args.dry_run:
            if cache_rows == 0:
                print("\n⚠️  DRY RUN: chart_data_cache is empty. Backfill must be done before pruning.")
                print("    Run without --dry-run first, or with --skip-backfill if cache already exists.")
            else:
                print(f"\nchart_data_cache already has {cache_rows:,} rows — ready for pruning.")
        elif not args.skip_backfill:
            cache_rows = step_backfill_cache()
            if cache_rows == 0:
                events_with_history = get_event_ids_with_history()
                if events_with_history:
                    print("⚠️  WARNING: No cache rows were backfilled but history data exists.")
        else:
            print(f"\nSkipping cache backfill (--skip-backfill). Cache has {cache_rows:,} rows.")

        # Step 2: Prune history
        history_deleted = step_prune_history(args.keep_minutes, args.dry_run)

        # Step 3: Cleanup chart_points
        cp_deleted = step_cleanup_chart_points(args.dry_run)

        # Summary
        print_summary(before_size, args.keep_minutes, args.dry_run, history_deleted, cp_deleted)

        if args.dry_run:
            print("\n⚠️  DRY RUN complete. No changes were made.")
            print("    Run without --dry-run to apply changes.")


if __name__ == '__main__':
    main()
