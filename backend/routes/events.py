# backend/routes/events.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from services.event_ingestion import TOP_PLAYERS_INTERVAL_MS, parse_and_store_event_data, refresh_event_top_data
from services.event_query_service import clear_event_query_cache, get_chart_series, get_top_players as get_top_players_data
from services.event_repository import (
    get_current_or_latest_event,
    get_event as find_event,
    get_scores as find_scores,
    list_events as find_events,
    serialize_event,
)

events_bp = Blueprint('events', __name__)

# Background thread pool for non-blocking data refreshes
_refresh_executor = ThreadPoolExecutor(max_workers=1)

# In-memory store for last refresh timestamps (event_id -> timestamp)
_last_refresh_time = {}
_last_top_players_refresh_time = {}
REFRESH_COOLDOWN = 30  # 30 seconds
MAX_CACHED_REFRESH_TIMES = 50


def _cleanup_refresh_times():
    """Remove oldest entries to prevent unbounded growth."""
    for d in (_last_refresh_time, _last_top_players_refresh_time):
        if len(d) > MAX_CACHED_REFRESH_TIMES * 2:
            sorted_keys = sorted(d.keys(), key=lambda k: d[k])
            for k in sorted_keys[:-MAX_CACHED_REFRESH_TIMES]:
                d.pop(k, None)


def _bg_refresh_event(app, event_id):
    """Refresh event data in background thread."""
    try:
        with app.app_context():
            app.logger.info(f"Background refresh for event {event_id}...")
            success = parse_and_store_event_data(event_id)
            if success:
                clear_event_query_cache()
            else:
                _last_refresh_time[event_id] = 0
    except Exception as e:
        _last_refresh_time[event_id] = 0
        app.logger.error(f"Background refresh failed for event {event_id}: {e}")


def _bg_refresh_top_players(app, event_id, interval):
    """Refresh top players data in background thread."""
    try:
        with app.app_context():
            app.logger.info(f"Background top_players refresh for event {event_id}...")
            refresh_event_top_data(event_id, interval=interval)
            clear_event_query_cache()
    except Exception as e:
        _last_top_players_refresh_time[event_id] = 0
        app.logger.error(f"Background top_players refresh failed for event {event_id}: {e}")

@events_bp.route('/', methods=['GET'])
def list_events():
    limit = int(request.args.get('limit', 1000))
    return jsonify([serialize_event(event) for event in find_events(limit)])

@events_bp.route('/<string:event_id>', methods=['GET'])
def get_event(event_id):
    _cleanup_refresh_times()
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
        if e:
            # Have stale data — return it immediately, refresh in background
            _refresh_executor.submit(_bg_refresh_event, current_app._get_current_object(), event_id)
        else:
            # No data at all — must refresh synchronously
            current_app.logger.info(f"Refreshing data for event {event_id}...")
            success = parse_and_store_event_data(event_id)
            if not success:
                if force_refresh:
                    _last_refresh_time[event_id] = 0
                return jsonify({'error': 'event not found'}), 404
            clear_event_query_cache()
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
    interval = int(request.args.get('interval', TOP_PLAYERS_INTERVAL_MS))
    event = find_event(event_id)
    if not event:
        parse_and_store_event_data(event_id)
        event = find_event(event_id)
        if not event:
            return jsonify({'error': 'event not found'}), 404

    refresh_requested = request.args.get('refresh') == 'true'
    force_refresh = request.args.get('force') == 'true'
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    is_active = event.start_at <= now_ms <= event.end_at
    now = time.time()
    last_refresh = _last_top_players_refresh_time.get(event_id, 0)
    can_refresh = force_refresh or now - last_refresh >= REFRESH_COOLDOWN
    if (is_active or force_refresh) and (refresh_requested or is_active) and can_refresh:
        _last_top_players_refresh_time[event_id] = now
        # Fire refresh in background — don't block the response
        _refresh_executor.submit(_bg_refresh_top_players, current_app._get_current_object(), event_id, interval)

    player_data = get_top_players_data(event_id, limit)
    if player_data is None:
        return jsonify({'error': 'event not found'}), 404
    return jsonify(player_data)