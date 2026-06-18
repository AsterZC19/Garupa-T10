# backend/services/statistics.py
import bisect
from models import PlayerScoreHistory, Event
from collections import defaultdict
from services.ttl_cache import TTLCache
from datetime import datetime

hourly_stats_cache = TTLCache(300)  # 5-minute cache for active events
hourly_stats_cache_ended = TTLCache(3600)  # 1-hour cache for ended events

def _find_index_le(timestamps, target):
    """Return index of rightmost value <= target, or -1 if all > target."""
    i = bisect.bisect_right(timestamps, target) - 1
    return i

def calculate_hourly_stats(event_id):
    """
    Calculates hourly statistics for top 10 players for a given event.
    - 时速 (hourly_speed): PT difference between points closest to hour boundaries.
    - 周回次数 (run_count): Number of times the score changes for a player in an hour.
    - 平均PT (average_pt): hourly_speed / run_count.
    """
    event_id_str = str(event_id)
    cached = hourly_stats_cache.get(event_id_str)
    if cached is not None:
        return cached
    cached = hourly_stats_cache_ended.get(event_id_str)
    if cached is not None:
        return cached

    event = Event.query.filter_by(event_id=event_id).first()
    if not event:
        return {"error": "Event not found"}

    history = PlayerScoreHistory.query.with_entities(
        PlayerScoreHistory.uid,
        PlayerScoreHistory.timestamp,
        PlayerScoreHistory.pt
    ).filter_by(event_id=event_id).order_by(PlayerScoreHistory.timestamp.asc()).all()
    if not history:
        return []

    # Group all score records by user ID
    scores_by_uid = defaultdict(list)
    for uid, timestamp, pt in history:
        scores_by_uid[uid].append((timestamp, pt))

    # Determine the range of hours
    min_ts = history[0].timestamp
    max_ts = history[-1].timestamp
    start_hour_ts = (min_ts // 3600000) * 3600000
    end_hour_ts = (max_ts // 3600000) * 3600000

    # Pre-compute per-user arrays with separate timestamp/pt lists for bisect
    user_arrays = {}
    for uid, scores in scores_by_uid.items():
        timestamps = [s[0] for s in scores]
        pts = [s[1] for s in scores]
        user_arrays[uid] = (timestamps, pts)

    hourly_stats = []
    current_hour_ts = start_hour_ts
    while current_hour_ts <= end_hour_ts:
        next_hour_ts = current_hour_ts + 3600000
        total_hourly_speed = 0
        total_run_count = 0

        for uid, (timestamps, pts) in user_arrays.items():
            # --- 1. Hourly Speed ---
            si = _find_index_le(timestamps, current_hour_ts)
            ei = _find_index_le(timestamps, next_hour_ts)
            if si >= 0 and ei > si:
                speed = pts[ei] - pts[si]
                if speed > 0:
                    total_hourly_speed += speed

            # --- 2. Run Count ---
            # Find indices bounding the hour window
            first_in = bisect.bisect_left(timestamps, current_hour_ts)
            last_in = _find_index_le(timestamps, next_hour_ts - 1)
            if last_in < first_in:
                continue

            last_pt = pts[first_in - 1] if first_in > 0 else pts[first_in]
            run_count = 0
            for i in range(first_in, last_in + 1):
                if pts[i] > last_pt:
                    run_count += 1
                last_pt = pts[i]
            total_run_count += run_count

        # --- 3. Average PT ---
        average_pt = (total_hourly_speed // total_run_count) if total_run_count > 0 else 0

        if total_hourly_speed > 0 or total_run_count > 0:
            hourly_stats.append({
                "hour_timestamp": current_hour_ts,
                "hourly_speed": total_hourly_speed,
                "run_count": total_run_count if total_run_count > 0 else '-',
                "average_pt": average_pt if total_run_count > 0 else '-'
            })

        current_hour_ts = next_hour_ts

    result = sorted(hourly_stats, key=lambda x: x['hour_timestamp'])

    # Use longer cache for ended events
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    if event.end_at > 0 and now_ms > event.end_at + 2 * 24 * 3600 * 1000:
        return hourly_stats_cache_ended.set(event_id_str, result)
    return hourly_stats_cache.set(event_id_str, result)