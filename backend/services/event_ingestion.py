from services.bestdori_client import BESTDORI, client
from services import event_repository as repo
from services.player_name_history import record_names
from services.ranking_snapshot import latest_snapshot_by_uid


def parse_server_value(value, default=None):
    if isinstance(value, list):
        return value[0] if value and value[0] is not None else default
    return value if value is not None else default


def resolve_banner_url(meta):
    asset_bundle_name = meta.get('assetBundleName')
    if asset_bundle_name:
        primary_url = f"{BESTDORI}/assets/jp/event/{asset_bundle_name}/images_rip/banner.png"
        if client.asset_exists(primary_url):
            return primary_url

    banner_asset_bundle_name = meta.get('bannerAssetBundleName')
    if banner_asset_bundle_name:
        fallback_url = f"{BESTDORI}/assets/jp/homebanner_rip/{banner_asset_bundle_name}.png"
        if client.asset_exists(fallback_url):
            return fallback_url

    return None


def upsert_event_from_meta(event_id, meta):
    name = parse_server_value(meta.get('eventName'), '')
    event_type = meta.get('eventType')
    start_at = parse_server_value(meta.get('startAt'), 0)
    end_at = parse_server_value(meta.get('endAt'), 0)
    banner_url = resolve_banner_url(meta)
    description = parse_server_value(meta.get('eventDescription'))
    return repo.upsert_event(event_id, name, event_type, start_at, end_at, banner_url, description)


def build_name_map(users):
    return {str(user.get('uid')): user.get('name', '') for user in users}


def keep_latest_point_per_minute(points):
    bucketed = {}
    for point in points:
        uid = str(point.get('uid'))
        timestamp = int(point.get('time'))
        minute_ts = (timestamp // 60000) * 60000
        bucket_key = (uid, minute_ts)
        if bucket_key not in bucketed or timestamp > bucketed[bucket_key]['source_time']:
            bucketed[bucket_key] = {
                'uid': uid,
                'time': minute_ts,
                'source_time': timestamp,
                'value': point.get('value')
            }
    return sorted(bucketed.values(), key=lambda point: (point['time'], point['uid']))


def build_score_rows(event_id, points, users):
    # users contains historical participants too; membership comes from the
    # newest raw snapshot, never from each player's last known score.
    current = latest_snapshot_by_uid(points)
    user_map = {str(user.get('uid')): user for user in users}
    rows = []
    for rank, item in enumerate(sorted(current.values(), key=lambda p: p['pt'], reverse=True), 1):
        user = user_map.get(item['uid'], {})
        rows.append({
            'event_id': str(event_id),
            'uid': item['uid'],
            'name': user.get('name') or item['uid'],
            'pt': item['pt'],
            'rank': rank,
            'signature': user.get('introduction') or '',
            'updated_at': item['timestamp'],
        })
    return rows


def compute_speeds_and_store(event_id, top_json, server='jp'):
    if top_json is None:
        return

    points = top_json.get('points', [])
    users = top_json.get('users', [])
    record_names(users, source=f'event:{server}:{event_id}')
    if not points:
        return  # Empty/failed upstream responses must not erase stored scores.

    if not repo.get_event(event_id):
        print(f"[Error] compute_speeds_and_store: Event {event_id} not found in DB.")
        return

    repo.replace_scores(event_id, build_score_rows(event_id, points, users))


TOP_PLAYERS_INTERVAL_MS = 60000

# Track last stored timestamp per event so the 1-min refresh only processes new data
_last_stored_ts = {}


def parse_and_store_event_data(event_id, server='jp'):
    meta = client.get_event_meta(event_id)
    if not meta:
        print(f"event meta {event_id} not found")
        return False

    upsert_event_from_meta(event_id, meta)
    top = client.get_event_top_data(event_id, server=server, interval=900000)
    if top is None:
        print("no top data")
        return True

    compute_speeds_and_store(event_id, top, server=server)
    return True


def build_history_rows(event_id, top_json):
    points = top_json.get('points', []) if top_json else []
    users = top_json.get('users', []) if top_json else []
    name_map = build_name_map(users)
    rows = []
    for point in keep_latest_point_per_minute(points):
        uid = str(point.get('uid'))
        name = name_map.get(uid)
        rows.append({
            'uid': uid,
            'name': name if name and name.strip() else uid,
            'pt': point.get('value'),
            'timestamp': point.get('time')
        })
    return rows


def backfill_event_history(event_id, server='jp', interval=60000):
    top = client.get_event_top_data(event_id, server=server, interval=interval)
    if top is None:
        return None
    record_names(top.get('users', []), source=f'event:{server}:{event_id}')
    rows = build_history_rows(event_id, top)
    return repo.append_player_score_history_if_missing(event_id, rows)


def refresh_event_top_data(event_id, server='jp', interval=TOP_PLAYERS_INTERVAL_MS):
    top = client.get_event_top_data(event_id, server=server, interval=interval)
    if top is None:
        return 0

    points = top.get('points', [])
    users = top.get('users', [])
    record_names(users, source=f'event:{server}:{event_id}')
    if not points:
        return 0

    # Keep historical points separately from current ranking membership.
    bucketed_points = keep_latest_point_per_minute(points)

    min_ts = _last_stored_ts.get(str(event_id), 0)

    repo.replace_scores(event_id, build_score_rows(event_id, points, users))

    # --- History rows (from bucketed points + name map) ---
    name_map = build_name_map(users)
    history_rows = []
    for p in bucketed_points:
        uid = p['uid']
        name = name_map.get(uid)
        history_rows.append({
            'uid': uid,
            'name': name if name and name.strip() else uid,
            'pt': p.get('value'),
            'timestamp': p['time']
        })

    result = repo.append_player_score_history_if_missing(event_id, history_rows, min_timestamp=min_ts)

    # Update last-stored timestamp cache so next run skips already-processed data
    if bucketed_points:
        max_ts = max(p['time'] for p in bucketed_points)
        _last_stored_ts[str(event_id)] = max(_last_stored_ts.get(str(event_id), 0), max_ts)

    return result


def record_active_event_top_10(server='jp'):
    active_event = repo.get_active_event()
    if not active_event:
        return 0

    return refresh_event_top_data(active_event.event_id, server=server, interval=TOP_PLAYERS_INTERVAL_MS)
