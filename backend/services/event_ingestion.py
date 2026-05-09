from datetime import datetime
from collections import defaultdict
from models import db, Event, Score, PlayerScoreHistory
from services.bestdori_client import BESTDORI, client
from services import event_repository as repo


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


def latest_points_by_uid(points):
    latest = {}
    for point in points:
        uid = str(point.get('uid'))
        timestamp = int(point.get('time'))
        pt = int(point.get('value', 0))
        if uid not in latest or timestamp > latest[uid]['timestamp']:
            latest[uid] = {'uid': uid, 'timestamp': timestamp, 'pt': pt}
    return latest


def build_name_map(users):
    return {str(user.get('uid')): user.get('name', '') for user in users}


def compute_speeds_and_store(event_id, top_json):
    if top_json is None:
        return

    points = top_json.get('points', [])
    users = top_json.get('users', [])
    latest_by_uid = latest_points_by_uid(points)

    chart_rows = [
        {'uid': str(point.get('uid')), 'timestamp': int(point.get('time')), 'pt': int(point.get('value', 0))}
        for point in points
    ]
    repo.append_chart_points_if_missing(event_id, chart_rows)

    event = repo.get_event(event_id)
    if not event:
        print(f"[Error] compute_speeds_and_store: Event {event_id} not found in DB.")
        return

    latest_data_timestamp = 0
    if points:
        latest_data_timestamp = max(point.get('time', 0) for point in points)
    if latest_data_timestamp == 0:
        current_time = repo.now_ms()
        latest_data_timestamp = event.end_at if current_time > event.end_at and event.end_at > 0 else current_time

    score_rows = []
    if users:
        for user in users:
            uid = str(user.get('uid'))
            score_rows.append({
                'event_id': str(event_id),
                'uid': uid,
                'name': user.get('name') or '',
                'pt': int(user.get('current_pt') or latest_by_uid.get(uid, {}).get('pt', 0)),
                'rank': user.get('ranking') or 0,
                'signature': user.get('introduction') or '',
                'updated_at': latest_data_timestamp
            })
    else:
        ranked = sorted(latest_by_uid.values(), key=lambda item: item['pt'], reverse=True)
        for index, item in enumerate(ranked, start=1):
            score_rows.append({
                'event_id': str(event_id),
                'uid': item['uid'],
                'name': item['uid'],
                'pt': item['pt'],
                'rank': index,
                'signature': '',
                'updated_at': latest_data_timestamp
            })

    repo.replace_scores(event_id, score_rows)


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

    compute_speeds_and_store(event_id, top)
    return True


def build_history_rows(event_id, top_json):
    points = top_json.get('points', []) if top_json else []
    users = top_json.get('users', []) if top_json else []
    name_map = build_name_map(users)
    rows = []
    for point in points:
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
    rows = build_history_rows(event_id, top)
    return repo.append_player_score_history_if_missing(event_id, rows)


def record_active_event_top_10(server='jp'):
    active_event = repo.get_active_event()
    if not active_event:
        return 0

    event_id = active_event.event_id
    top = client.get_event_top_data(event_id, server=server, interval=900000)
    if top is None:
        return 0

    points = top.get('points', [])
    users = top.get('users', [])
    if not points:
        return 0

    latest_scores = latest_points_by_uid(points)
    ranking = sorted(latest_scores.values(), key=lambda item: item['pt'], reverse=True)[:10]
    user_meta_map = {str(user.get('uid')): user for user in users}

    score_rows = []
    history_rows = []
    for index, item in enumerate(ranking, start=1):
        uid = item['uid']
        meta = user_meta_map.get(uid, {})
        name = meta.get('name')
        final_name = name if name and name.strip() else uid
        score_rows.append({
            'event_id': str(event_id),
            'uid': uid,
            'name': final_name,
            'pt': item['pt'],
            'rank': index,
            'signature': meta.get('introduction', ''),
            'updated_at': item['timestamp']
        })
        history_rows.append({
            'uid': uid,
            'name': final_name,
            'pt': item['pt'],
            'timestamp': item['timestamp']
        })

    repo.replace_scores(event_id, score_rows)
    return repo.append_player_score_history_if_missing(event_id, history_rows)
