# backend/routes/events.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import time
from services.event_ingestion import parse_and_store_event_data
from services.event_query_service import clear_event_query_cache, get_chart_series, get_top_players as get_top_players_data
from services.event_repository import (
    get_current_or_latest_event,
    get_event as find_event,
    get_scores as find_scores,
    list_events as find_events,
    serialize_event,
)

events_bp = Blueprint('events', __name__)

# In-memory store for last refresh timestamps (event_id -> timestamp)
_last_refresh_time = {}
REFRESH_COOLDOWN = 30  # 30 seconds

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
        clear_event_query_cache()
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
    event = find_event(event_id)
    if not event:
        return jsonify({'error': 'event not found'}), 404
    return jsonify(get_chart_series(event_id, requested_interval))

@events_bp.route('/<string:event_id>/top_players', methods=['GET'])
def get_top_players(event_id):
    limit = int(request.args.get('limit', 10))
    event = find_event(event_id)
    if not event:
        parse_and_store_event_data(event_id)
        event = find_event(event_id)
        if not event:
            return jsonify({'error': 'event not found'}), 404

    player_data = get_top_players_data(event_id, limit)
    if player_data is None:
        return jsonify({'error': 'event not found'}), 404
    return jsonify(player_data)