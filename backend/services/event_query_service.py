from collections import defaultdict
from datetime import datetime
from services import event_repository as repo
from services.ttl_cache import TTLCache


chart_cache = TTLCache(120)
chart_cache_ended = TTLCache(3600)  # 1 hour for long-ended events
top_players_cache = TTLCache(60)
MAX_CHART_POINTS_PER_SERIES = 300


def clear_event_query_cache():
    chart_cache.clear()
    chart_cache_ended.clear()
    top_players_cache.clear()


def row_timestamp(row):
    return row.timestamp


def row_pt(row):
    return row.pt


def _downsample_points(points, max_points):
    """Downsample a sorted list of {t, pt} dicts to at most max_points, preserving peaks."""
    if len(points) <= max_points:
        return points

    result = [points[0]]
    remaining_slots = max_points - 2  # reserve for first and last
    if remaining_slots <= 0:
        result.append(points[-1])
        return result

    inner = points[1:-1]
    bucket_size = max(1, len(inner) // remaining_slots)

    for i in range(0, len(inner), bucket_size):
        bucket = inner[i:i + bucket_size]
        # pick the point with the highest pt in each bucket to preserve peaks
        result.append(max(bucket, key=lambda p: p['pt']))

    result.append(points[-1])
    return result


def find_closest_point(scores, target_ts):
    if not scores:
        return None
    return min(scores, key=lambda score: abs(row_timestamp(score) - target_ts))


def find_last_point_before(scores, target_ts):
    relevant_scores = [score for score in scores if row_timestamp(score) < target_ts]
    return relevant_scores[-1] if relevant_scores else None


def get_chart_series(event_id, interval='15m'):
    cache_key = (str(event_id), interval)
    cached = chart_cache.get(cache_key)
    if cached is not None:
        return cached
    cached = chart_cache_ended.get(cache_key)
    if cached is not None:
        return cached

    bucket_ms = 3600000 if interval == '1h' else 900000
    rows = repo.get_chart_history_aggregated(event_id, bucket_ms)
    if not rows:
        # Fallback to chart_points table (populated by parse_and_store_event_data)
        rows = repo.get_chart_history_aggregated_fallback(event_id, bucket_ms)
    if not rows:
        return {}

    # SQL already aggregated: (uid, name, bucket_ts, pt), one row per uid per bucket
    user_points = defaultdict(list)
    name_map = {}
    for uid, name, bucket_ts, pt in rows:
        name_map[uid] = name or uid
        user_points[uid].append({'t': bucket_ts, 'pt': pt})

    series = {}
    for uid, points_list in user_points.items():
        points_list.sort(key=lambda p: p['t'])
        sampled = _downsample_points(points_list, MAX_CHART_POINTS_PER_SERIES)
        series[uid] = {'name': name_map.get(uid, uid), 'points': sampled}

    # Use longer effective cache for ended events
    event = repo.get_event(event_id)
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    if event and event.end_at > 0 and now_ms > event.end_at + 24 * 3600 * 1000:
        return chart_cache_ended.set(cache_key, series)
    return chart_cache.set(cache_key, series)


def get_top_players(event_id, limit=10):
    cache_key = (str(event_id), limit)
    cached = top_players_cache.get(cache_key)
    if cached is not None:
        return cached

    event = repo.get_event(event_id)
    if not event:
        return None

    current_time_ms = int(datetime.now().timestamp() * 1000)
    anchor_ts = current_time_ms if current_time_ms < event.end_at else event.end_at
    end_ts = (anchor_ts // 3600000) * 3600000
    start_ts = end_ts - 3600000
    is_new_event = event.start_at > start_ts

    top_scores = repo.get_top_scores(event_id, limit)
    if not top_scores:
        return []

    top_player_uids = [score.uid for score in top_scores]
    history_records = repo.get_history_for_uids(event_id, top_player_uids)

    scores_by_uid = defaultdict(list)
    for record in history_records:
        scores_by_uid[record.uid].append(record)

    player_data = []
    for index, score in enumerate(top_scores):
        player_history = scores_by_uid[score.uid]
        hourly_speed = 0
        run_count = 0
        average_pt = 0

        if player_history and not is_new_event:
            start_point = find_closest_point(player_history, start_ts)
            end_point = find_closest_point(player_history, end_ts)

            if start_point and end_point and row_timestamp(start_point) < row_timestamp(end_point):
                time_diff_h = (row_timestamp(end_point) - row_timestamp(start_point)) / 3600000
                if time_diff_h > 0:
                    speed = (row_pt(end_point) - row_pt(start_point)) / time_diff_h
                    hourly_speed = round(speed) if speed > 0 else 0

            scores_in_hour = [record for record in player_history if start_ts <= row_timestamp(record) < end_ts]
            if scores_in_hour:
                last_score_before_hour = find_last_point_before(player_history, start_ts)
                last_pt = row_pt(last_score_before_hour) if last_score_before_hour else row_pt(scores_in_hour[0])

                for record in scores_in_hour:
                    if row_pt(record) > last_pt:
                        run_count += 1
                    last_pt = row_pt(record)

            if run_count > 0:
                average_pt = hourly_speed // run_count

        player_data.append({
            'uid': score.uid,
            'name': score.name,
            'pt': score.pt,
            'rank': score.rank or index + 1,
            'signature': score.signature,
            'score_updated_at': score.updated_at,
            'hourly_speed': hourly_speed,
            'run_count': run_count if run_count > 0 else '-',
            'average_pt': average_pt if run_count > 0 else '-',
            'speed_rank': 0
        })

    player_data.sort(key=lambda player: player['hourly_speed'], reverse=True)
    for index, player in enumerate(player_data):
        player['speed_rank'] = index + 1

    player_data.sort(key=lambda player: player['rank'])
    return top_players_cache.set(cache_key, player_data)
