# backend/routes/events.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import time # Added for cooldown
from models import db
from models import Event, Score, ChartPoint
from services.fetcher import parse_and_store_event_data

events_bp = Blueprint('events', __name__)

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
        # Check if the event is ongoing or has ended recently (e.g., within the last 2 days)
        is_recent_or_ongoing = e.end_at > (now_ms - 2 * 24 * 3600 * 1000)
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
        parse_and_store_event_data(event_id)
        event = Event.query.filter_by(event_id=event_id).first()
        if not event:
            return jsonify({'error': 'event not found'}), 404

    pts = ChartPoint.query.filter(
        ChartPoint.event_id == event_id,
        ChartPoint.timestamp >= event.start_at,
        ChartPoint.timestamp <= event.end_at
    ).order_by(ChartPoint.timestamp.asc()).all()
    
    # Group points by user first
    user_points_raw = {}
    for p in pts:
        if p.uid not in user_points_raw:
            user_points_raw[p.uid] = {'name': p.name or p.uid, 'points': []}
        user_points_raw[p.uid]['points'].append(p)

    # Down-sample for each user
    series = {}
    for uid, data in user_points_raw.items():
        bucketed_points = {}
        # 15 minutes = 900,000 milliseconds
        for p in data['points']:
            bucket_key = p.timestamp // 900000
            bucketed_points[bucket_key] = {'t': p.timestamp, 'pt': p.pt}
        
        sampled_points = sorted(bucketed_points.values(), key=lambda x: x['t'])
        series[uid] = {'name': data['name'], 'points': sampled_points}

    return jsonify(series)

@events_bp.route('/<string:event_id>/top_players', methods=['GET'])
def get_top_players(event_id):
    event = Event.query.filter_by(event_id=event_id).first()
    if not event:
        parse_and_store_event_data(event_id)
        event = Event.query.filter_by(event_id=event_id).first()
        if not event:
            return jsonify({'error': 'event not found'}), 404

    limit = int(request.args.get('limit', 10))

    # Determine the anchor time for the hourly speed calculation
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    anchor_ts = now_ms
    # If the event has ended, use the event's end time as the anchor
    if now_ms > event.end_at:
        anchor_ts = event.end_at

    # Default to the last completed hour based on the anchor time
    end_ts = (anchor_ts // 3600000) * 3600000
    start_ts = end_ts - 3600000

    # Fetch top players
    scores_to_process = Score.query.filter_by(event_id=event_id).order_by(Score.pt.desc()).limit(100).all()
    
    latest_updated_at = db.session.query(db.func.max(Score.updated_at)).filter_by(event_id=event_id).scalar()

    player_data = []
    for i, s in enumerate(scores_to_process):
        # Find points around the hour block
        p_start = ChartPoint.query.filter(
            ChartPoint.event_id == event_id,
            ChartPoint.uid == s.uid,
            ChartPoint.timestamp <= start_ts,
            ChartPoint.timestamp >= event.start_at
        ).order_by(ChartPoint.timestamp.desc()).first()

        p_end = ChartPoint.query.filter(
            ChartPoint.event_id == event_id,
            ChartPoint.uid == s.uid,
            ChartPoint.timestamp <= end_ts,
            ChartPoint.timestamp >= event.start_at
        ).order_by(ChartPoint.timestamp.desc()).first()
        
        speed = 0
        if p_start and p_end and p_end.timestamp > p_start.timestamp:
            time_diff_h = (p_end.timestamp - p_start.timestamp) / 3600000
            if time_diff_h > 0:
                speed = round((p_end.pt - p_start.pt) / time_diff_h)

        player_data.append({
            'uid': s.uid,
            'name': s.name,
            'pt': s.pt,
            'rank': i + 1,
            'signature': s.signature,
            'speed_data_timestamp': end_ts, # Renamed from updated_at
            'score_updated_at': s.updated_at, # Added for the new column
            'speed_last_hour': speed,
            'speed_rank': 0 
        })

    # Calculate speed rank
    player_data.sort(key=lambda p: p['speed_last_hour'], reverse=True)
    for i, player in enumerate(player_data):
        player['speed_rank'] = i + 1
        
    # Sort back by original rank (which is now based on PT)
    player_data.sort(key=lambda p: p['rank'])
    
    return jsonify(player_data[:limit])