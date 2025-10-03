# backend/routes/events.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import time # Added for cooldown
from models import db
from models import Event, Score, ChartPoint, PlayerScoreHistory
from services.fetcher import parse_and_store_event_data
from collections import defaultdict

events_bp = Blueprint('events', __name__)

# Helper functions for statistics
def find_closest_point(scores, target_ts):
    if not scores: return None
    return min(scores, key=lambda s: abs(s.timestamp - target_ts))

def find_last_point_before(scores, target_ts):
    relevant_scores = [s for s in scores if s.timestamp < target_ts]
    return relevant_scores[-1] if relevant_scores else None

# In-memory store for last refresh timestamps (event_id -> timestamp)
_last_refresh_time = {}
REFRESH_COOLDOWN = 30  # 30 seconds

@events_bp.route('/', methods=['GET'])
def list_events():
    evs = Event.query.order_by(Event.start_at.desc()).all()
    return jsonify([{
        'event_id': e.event_id,
        'name': e.name,
        'type': e.event_type,
        'start_at': e.start_at,
        'end_at': e.end_at,
        'banner_url': e.banner_url,
        'description': e.description
    } for e in evs])

@events_bp.route('/<string:event_id>', methods=['GET'])
def get_event(event_id):
    e = Event.query.filter_by(event_id=event_id).first()

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
                return jsonify({
                    'event_id': e.event_id,
                    'name': e.name,
                    'type': e.event_type,
                    'start_at': e.start_at,
                    'end_at': e.end_at,
                    'banner_url': e.banner_url,
                    'description': e.description
                })
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
        # Re-fetch from DB to get the updated data
        e = Event.query.filter_by(event_id=event_id).first()
        if not e:
            return jsonify({'error': 'event not found after fetching'}), 404

    return jsonify({
        'event_id': e.event_id,
        'name': e.name,
        'type': e.event_type,
        'start_at': e.start_at,
        'end_at': e.end_at,
        'banner_url': e.banner_url,
        'description': e.description
    })

@events_bp.route('/current', methods=['GET'])
def current_or_last():
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    current = Event.query.filter(Event.start_at <= now_ms, Event.end_at >= now_ms).order_by(Event.start_at.desc()).first()
    if current:
        e = current
        is_current = True
    else:
        e = Event.query.filter(Event.end_at < now_ms).order_by(Event.end_at.desc()).first()
        is_current = False
    if not e:
        return jsonify({'error': 'no event'}), 404
    return jsonify({'event': {
        'event_id': e.event_id,
        'name': e.name,
        'type': e.event_type,
        'start_at': e.start_at,
        'end_at': e.end_at,
        'banner_url': e.banner_url,
        'description': e.description
    }, 'is_current': is_current})

@events_bp.route('/<string:event_id>/scores', methods=['GET'])
def get_scores(event_id):
    event = Event.query.filter_by(event_id=event_id).first()
    if not event:
        parse_and_store_event_data(event_id)

    limit = int(request.args.get('limit', 50))
    scores = Score.query.filter_by(event_id=event_id).order_by(Score.rank.asc()).limit(limit).all()
    return jsonify([{
        'uid': s.uid, 'name': s.name, 'pt': s.pt, 'rank': s.rank, 'signature': s.signature, 'updated_at': s.updated_at
    } for s in scores])

@events_bp.route('/<string:event_id>/chart', methods=['GET'])
def get_chart(event_id):
    event = Event.query.filter_by(event_id=event_id).first()
    if not event:
        return jsonify({'error': 'event not found'}), 404

    # 1. Fetch all historical points for the event from the high-resolution table
    all_history_points = PlayerScoreHistory.query.filter_by(event_id=event_id).order_by(PlayerScoreHistory.timestamp.asc()).all()
    if not all_history_points:
        return jsonify({})

    # 2. Get all unique UIDs that have ever appeared in the history for this event
    all_uids_in_history = list(set([p.uid for p in all_history_points]))

    # 3. Get the most recent names for these UIDs from the PlayerScoreHistory table itself
    # We can get distinct UIDs and their latest names from the history
    # This is a bit tricky as name can change, so we'll just take the name from the latest point for each UID
    name_map = {}
    for p in all_history_points:
        name_map[p.uid] = p.name # Overwrite with later names, effectively getting the latest

    # 4. Group all points by user
    user_points_raw = defaultdict(list)
    for p in all_history_points:
        user_points_raw[p.uid].append(p)

    series = {}
    # 5. Down-sample for each user to 15-minute intervals
    for uid, points_list in user_points_raw.items():
        bucketed_points = {}
        # 15 minutes = 900,000 milliseconds
        for p in points_list:
            bucket_key = p.timestamp // 900000
            # Keep the last point in each 15-min bucket
            bucketed_points[bucket_key] = {'t': p.timestamp, 'pt': p.pt}
        
        if not bucketed_points:
            continue

        sampled_points = sorted(bucketed_points.values(), key=lambda x: x['t'])
        series[uid] = {'name': name_map.get(uid, uid), 'points': sampled_points}

    return jsonify(series)

@events_bp.route('/<string:event_id>/top_players', methods=['GET'])
def get_top_players(event_id):
    event = Event.query.filter_by(event_id=event_id).first()
    if not event:
        # Try to fetch it if it doesn't exist
        parse_and_store_event_data(event_id)
        event = Event.query.filter_by(event_id=event_id).first()
        if not event:
            return jsonify({'error': 'event not found'}), 404

    limit = int(request.args.get('limit', 10))

    # Determine the anchor time for the hourly calculation
    now_ms = int(datetime.now().timestamp() * 1000)
    anchor_ts = now_ms if now_ms < event.end_at else event.end_at
    
    # Last completed hour
    end_ts = (anchor_ts // 3600000) * 3600000
    start_ts = end_ts - 3600000

    # Handle new events: if the event started after the beginning of our calculation window, it's too new.
    is_new_event = (event.start_at > start_ts)

    # Get top players from the main Score table (snapshot)
    top_scores = Score.query.filter_by(event_id=event_id).order_by(Score.pt.desc()).limit(limit).all()
    if not top_scores:
        return jsonify([])

    # Get all historical data for these top players in one query
    top_player_uids = [s.uid for s in top_scores]
    history_records = PlayerScoreHistory.query.filter(
        PlayerScoreHistory.event_id == event_id,
        PlayerScoreHistory.uid.in_(top_player_uids)
    ).order_by(PlayerScoreHistory.timestamp.asc()).all()

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
            
            if start_point and end_point and start_point.timestamp < end_point.timestamp:
                time_diff_h = (end_point.timestamp - start_point.timestamp) / 3600000
                if time_diff_h > 0:
                    speed = (end_point.pt - start_point.pt) / time_diff_h
                    hourly_speed = round(speed) if speed > 0 else 0

            # 2. Calculate Run Count for the last hour
            scores_in_hour = [rec for rec in player_history if start_ts <= rec.timestamp < end_ts]
            if scores_in_hour:
                last_score_before_hour = find_last_point_before(player_history, start_ts)
                last_pt = last_score_before_hour.pt if last_score_before_hour else scores_in_hour[0].pt
                
                for rec in scores_in_hour:
                    if rec.pt > last_pt:
                        run_count += 1
                    last_pt = rec.pt

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
    
    return jsonify(player_data)