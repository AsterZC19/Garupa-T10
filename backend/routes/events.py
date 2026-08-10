# backend/routes/events.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from services.event_ingestion import TOP_PLAYERS_INTERVAL_MS, parse_and_store_event_data, refresh_event_top_data
from services.event_query_service import (
    clear_event_query_cache,
    get_chart_series,
    get_heatmap,
    get_top_players as get_top_players_data,
)
from services.heatmap import compute_heatmap_cache
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
_last_heatmap_refresh_time = {}
REFRESH_COOLDOWN = 30  # 30 seconds
MAX_CACHED_REFRESH_TIMES = 50


def _cleanup_refresh_times():
    """Remove oldest entries to prevent unbounded growth."""
    for d in (_last_refresh_time, _last_top_players_refresh_time, _last_heatmap_refresh_time):
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


def _bg_refresh_heatmap(app, event_id):
    """Precompute & store the heatmap cache in background (doesn't block the response)."""
    try:
        with app.app_context():
            app.logger.info(f"Background heatmap refresh for event {event_id}...")
            compute_heatmap_cache(event_id)
            clear_event_query_cache()
    except Exception as e:
        _last_heatmap_refresh_time[event_id] = 0
        app.logger.error(f"Background heatmap refresh failed for event {event_id}: {e}")


def _ensure_event(event_id):
    """确保活动存在并返回；本地缺失时尝试从 Bestdori 拉取，仍无则返回 None。"""
    event = find_event(event_id)
    if not event:
        parse_and_store_event_data(event_id)
        event = find_event(event_id)
    return event

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
    event = _ensure_event(event_id)
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

def _heatmap_refresh_worthwhile(event_id):
    """缓存为空时是否值得后台刷新：只对进行中或近期（7 天内）结束的活动刷新，
    避免对未开始 / 无数据的远古活动反复请求 Bestdori。"""
    event = find_event(event_id)
    if not event:
        return False
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    if event.start_at > now_ms:  # 未开始：Bestdori 还没有数据，没必要刷
        return False
    if event.end_at >= now_ms:  # 进行中
        return True
    return event.end_at > 0 and (now_ms - event.end_at) <= 7 * 24 * 3600 * 1000


@events_bp.route('/<string:event_id>/heatmap', methods=['GET'])
def get_heatmap_route(event_id):
    """top N 玩家的 48h 活跃热力图（读预计算缓存，不请求 Bestdori）。

    缓存由调度器每小时预计算落库（services.heatmap）。若缓存为空且活动进行中/
    刚结束（用户当前在看），在后台触发一次预计算并立即返回空结果，不阻塞页面。

    uids 查询参数：前端把表格展示的玩家 uid 列表（逗号分隔）传进来，只返回这些
    玩家并据此归一化颜色，保证与展示行一致。
    """
    limit = int(request.args.get('limit', 10))
    hours = int(request.args.get('hours', 48))
    uids_raw = request.args.get('uids', '')
    uids = [u for u in uids_raw.split(',') if u] if uids_raw else None

    result = get_heatmap(event_id, limit=limit, hours=hours, uids=uids)

    # 缓存为空（ref_ts==0）→ 后台预计算（带冷却，不阻塞响应）
    if result['ref_ts'] == 0 and _heatmap_refresh_worthwhile(event_id):
        now = time.time()
        if now - _last_heatmap_refresh_time.get(event_id, 0) >= REFRESH_COOLDOWN:
            _last_heatmap_refresh_time[event_id] = now
            _refresh_executor.submit(_bg_refresh_heatmap, current_app._get_current_object(), event_id)

    return jsonify(result)