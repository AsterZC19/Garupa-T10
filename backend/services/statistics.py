# backend/services/statistics.py
from models import db, PlayerScoreHistory, Event
from sqlalchemy import and_
from collections import defaultdict
import time

def find_closest_point(scores, target_ts):
    """Finds the score point closest to a target timestamp."""
    if not scores:
        return None
    return min(scores, key=lambda s: abs(s[0] - target_ts))

def find_last_point_before(scores, target_ts):
    """Finds the last score point strictly before a target timestamp."""
    relevant_scores = [s for s in scores if s[0] < target_ts]
    return relevant_scores[-1] if relevant_scores else None

def calculate_hourly_stats(event_id):
    """
    Calculates hourly statistics for top 10 players for a given event.
    - 时速 (hourly_speed): PT difference between points closest to hour boundaries.
    - 周回次数 (run_count): Number of times the score changes for a player in an hour.
    - 平均PT (average_pt): hourly_speed / run_count.
    """
    event = Event.query.filter_by(event_id=event_id).first()
    if not event:
        return {"error": "Event not found"}

    history = PlayerScoreHistory.query.filter_by(event_id=event_id).order_by(PlayerScoreHistory.timestamp.asc()).all()
    if not history:
        return []

    # Group all score records by user ID
    scores_by_uid = defaultdict(list)
    for record in history:
        scores_by_uid[record.uid].append((record.timestamp, record.pt))

    # Determine the range of hours to generate stats for
    min_ts = history[0].timestamp
    max_ts = history[-1].timestamp
    start_hour_ts = (min_ts // 3600000) * 3600000
    end_hour_ts = (max_ts // 3600000) * 3600000
    
    all_uids = list(scores_by_uid.keys())
    hourly_stats = []

    # Iterate through each hour from the start to the end of the event data
    current_hour_ts = start_hour_ts
    while current_hour_ts <= end_hour_ts:
        next_hour_ts = current_hour_ts + 3600000
        
        total_hourly_speed = 0
        total_run_count = 0

        for uid in all_uids:
            player_scores = scores_by_uid[uid]

            # --- 1. Calculate Hourly Speed (时速) ---
            start_point = find_closest_point(player_scores, current_hour_ts)
            end_point = find_closest_point(player_scores, next_hour_ts)

            if start_point and end_point and start_point[0] < end_point[0]:
                speed = end_point[1] - start_point[1]
                if speed > 0:
                    total_hourly_speed += speed

            # --- 2. Calculate Run Count (周回次数) ---
            scores_in_hour = [s for s in player_scores if current_hour_ts <= s[0] < next_hour_ts]
            if not scores_in_hour:
                continue

            # Find the last score from before this hour to establish a baseline PT
            last_score_before_hour = find_last_point_before(player_scores, current_hour_ts)
            
            # If no score before, use the first score of the hour as the baseline
            last_pt = last_score_before_hour[1] if last_score_before_hour else scores_in_hour[0][1]
            
            run_count = 0
            # Count score increases within the hour
            for _, pt in sorted(scores_in_hour): # Ensure they are in order
                if pt > last_pt:
                    run_count += 1
                last_pt = pt
            
            total_run_count += run_count

        # --- 3. Calculate Average PT (平均PT) ---
        average_pt = (total_hourly_speed // total_run_count) if total_run_count > 0 else 0

        # Only add stats if there was activity
        if total_hourly_speed > 0 or total_run_count > 0:
            hourly_stats.append({
                "hour_timestamp": current_hour_ts,
                "hourly_speed": total_hourly_speed,
                "run_count": total_run_count if total_run_count > 0 else '-',
                "average_pt": average_pt if total_run_count > 0 else '-'
            })
        
        current_hour_ts = next_hour_ts

    return sorted(hourly_stats, key=lambda x: x['hour_timestamp'])