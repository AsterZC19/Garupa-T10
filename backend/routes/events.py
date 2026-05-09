# backend/routes/events.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import time
from collections import defaultdict
from services.event_ingestion import parse_and_store_event_data
from services.event_repository import (
    get_chart_history,
    get_current_or_latest_event,
    get_event as find_event,
    get_history_for_uids,
    get_scores as find_scores,
    get_top_scores,
    list_events as find_events,
    serialize_event,
)
from services.ttl_cache import TTLCache

events_bp = Blueprint('events', __name__)

# Helper functions for statistics
def row_timestamp(row):
    return row.timestamp


def row_pt(row):
    return row.pt


def find_closest_point(scores, target_ts):
    if not scores: return None
    return min(scores, key=lambda s: abs(row_timestamp(s) - target_ts))


def find_last_point_before(scores, target_ts):
    relevant_scores = [s for s in scores if row_timestamp(s) < target_ts]
    return relevant_scores[-1] if relevant_scores else None

# In-memory store for last refresh timestamps (event_id -> timestamp)
_last_refresh_time = {}
REFRESH_COOLDOWN = 30  # 30 seconds
_chart_cache = TTLCache(60)
_top_players_cache = TTLCache(60)

@events_bp.route('/', methods=['GET'])
def list_events():
    return jsonify([serialize_event(event) for event in find_events()])

@events_bp.route('/<string:event_id>', methods=['GET'])
def get_event(event_id):
    e = find_event(event_id)

    # Refresh data if it's missing, forced, or older than 15 minutes
    force_refresh = request.args.get('force') == 'true'
    refresh_needed = False

    if force_refresh:
        now = time.time()
        last_refresh = _last_refresh_time.get(event_id, 0)
        if now - last_refresh < REFRESH_COOLDOWN:
            current_app.logger.info(f"Skipping force refresh for event {event_id} due to cooldown.")
            # If we have existing data, return it, otherwise indicate error
            if e:
                return jsonify(serialize_event(e))
            else:
                return jsonify({'error': 'event not found and refresh on cooldown'}), 404
        else:
            refresh_needed = True
            _last_refresh_time[event_id] = now # Tentatively set time
    elif not e:
        refresh_needed = True
    else:
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        # Check if the event is ongoing or has ended recently (e.g., within the last 2 days) + 30 min grace period
        GRACE_PERIOD_MS = 30 * 60 * 1000 # 30 minutes in milliseconds
        is_recent_or_ongoing = (e.end_at + GRACE_PERIOD_MS) > (now_ms - 2 * 24 * 3600 * 1000)
        if is_recent_or_ongoing and (now_ms - e.updated_at) > (15 * 60 * 1000):
            refresh_needed = True

    if refresh_needed:
        current_app.logger.info(f"Refreshing data for event {event_id}...")
        success = parse_and_store_event_data(event_id)
        if not success:
            # If fetch fails, we might still proceed with stale data if it exists
            if force_refresh: # if we failed, roll back the timestamp so user can try again sooner
                _last_refresh_time[event_id] = 0
            if not e:
                return jsonify({'error': 'event not found'}), 404
        _chart_cache.clear()
        _top_players_cache.clear()
        # Re-fetch from DB to get the updated data
        e = find_event(event_id)
        if not e:
            return jsonify({'error': 'event not found after fetching'}), 404

    return jsonify(serialize_event(e))

@events_bp.route('/current', methods=['GET'])
def current_or_last():
    e, is_current = get_current_or_latest_event()
    if not e:
        return jsonify({'error': 'no event'}), 404
    return jsonify({'event': serialize_event(e), 'is_current': is_current})

@events_bp.route('/<string:event_id>/scores', methods=['GET'])
def get_scores(event_id):
    event = find_event(event_id)
    if not event:
        parse_and_store_event_data(event_id)

    limit = int(request.args.get('limit', 50))
    scores = find_scores(event_id, limit)
    return jsonify([{
        'uid': s.uid, 'name': s.name, 'pt': s.pt, 'rank': s.rank, 'signature': s.signature, 'updated_at': s.updated_at
    } for s in scores])

@events_bp.route('/<string:event_id>/chart', methods=['GET'])
def get_chart(event_id):
    requested_interval = request.args.get('interval', '15m')
    cache_key = (event_id, requested_interval)
    cached = _chart_cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    event = find_event(event_id)
    if not event:
        return jsonify({'error': 'event not found'}), 404

    rows = get_chart_history(event_id)
    if not rows:
        return jsonify({})

    name_map = {}
    user_points_raw = defaultdict(list)
    for uid, name, timestamp, pt in rows:
        name_map[uid] = name
        user_points_raw[uid].append((timestamp, pt))

    series = {}
    if requested_interval == '1h':
        bucket_ms = 3600000
    else:
        bucket_ms = 900000

    for uid, points_list in user_points_raw.items():
        bucketed_points = {}
        for timestamp, pt in points_list:
            bucket_key = timestamp // bucket_ms
            bucketed_points[bucket_key] = {'t': timestamp, 'pt': pt}

        if not bucketed_points:
            continue

        sampled_points = sorted(bucketed_points.values(), key=lambda x: x['t'])
        series[uid] = {'name': name_map.get(uid, uid), 'points': sampled_points}

    return jsonify(_chart_cache.set(cache_key, series))

@events_bp.route('/<string:event_id>/top_players', methods=['GET'])
def get_top_players(event_id):
    limit = int(request.args.get('limit', 10))
    cache_key = (event_id, limit)
    cached = _top_players_cache.get(cache_key)
    if cached is not None:
        return jsonify(cached)

    event = find_event(event_id)
    if not event:
        # Try to fetch it if it doesn't exist
        parse_and_store_event_data(event_id)
        event = find_event(event_id)
        if not event:
            return jsonify({'error': 'event not found'}), 404

    # Determine the anchor time for the hourly calculation
    now_ms = int(datetime.now().timestamp() * 1000)
    anchor_ts = now_ms if now_ms < event.end_at else event.end_at
    
    # Last completed hour
    end_ts = (anchor_ts // 3600000) * 3600000
    start_ts = end_ts - 3600000

    # Handle new events: if the event started after the beginning of our calculation window, it's too new.
    is_new_event = (event.start_at > start_ts)

    # Get top players from the main Score table (snapshot)
    top_scores = get_top_scores(event_id, limit)
    if not top_scores:
        return jsonify([])

    # Get all historical data for these top players in one query
    top_player_uids = [s.uid for s in top_scores]
    history_records = get_history_for_uids(event_id, top_player_uids)

    # Group history by uid for easier processing
    scores_by_uid = defaultdict(list)
    for record in history_records:
        scores_by_uid[record.uid].append(record)

    player_data = []
    for i, s in enumerate(top_scores):
        player_history = scores_by_uid[s.uid]
        
        hourly_speed = 0
        run_count = 0
        average_pt = 0

        if player_history and not is_new_event:
            # 1. Calculate Hourly Speed
            start_point = find_closest_point(player_history, start_ts)
            end_point = find_closest_point(player_history, end_ts)
            
            if start_point and end_point and row_timestamp(start_point) < row_timestamp(end_point):
                time_diff_h = (row_timestamp(end_point) - row_timestamp(start_point)) / 3600000
                if time_diff_h > 0:
                    speed = (row_pt(end_point) - row_pt(start_point)) / time_diff_h
                    hourly_speed = round(speed) if speed > 0 else 0

            # 2. Calculate Run Count for the last hour
            scores_in_hour = [rec for rec in player_history if start_ts <= row_timestamp(rec) < end_ts]
            if scores_in_hour:
                last_score_before_hour = find_last_point_before(player_history, start_ts)
                last_pt = row_pt(last_score_before_hour) if last_score_before_hour else row_pt(scores_in_hour[0])
                
                for rec in scores_in_hour:
                    if row_pt(rec) > last_pt:
                        run_count += 1
                    last_pt = row_pt(rec)

            # 3. Calculate Average PT
            if run_count > 0:
                average_pt = hourly_speed // run_count
        
        # Compile player data
        player_data.append({
            'uid': s.uid,
            'name': s.name,
            'pt': s.pt,
            'rank': i + 1,
            'signature': s.signature,
            'score_updated_at': s.updated_at,
            'hourly_speed': hourly_speed,
            'run_count': run_count if run_count > 0 else '-',
            'average_pt': average_pt if run_count > 0 else '-',
            'speed_rank': 0 # Placeholder, will be calculated next
        })

    # Calculate speed rank
    player_data.sort(key=lambda p: p['hourly_speed'], reverse=True)
    for i, player in enumerate(player_data):
        player['speed_rank'] = i + 1
        
    # Sort back by original PT rank
    player_data.sort(key=lambda p: p['rank'])

    return jsonify(_top_players_cache.set(cache_key, player_data))