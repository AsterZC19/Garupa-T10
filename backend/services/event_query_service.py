import datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo
from datetime import datetime
from services import event_repository as repo
from services.ttl_cache import TTLCache


chart_cache = TTLCache(120)
chart_cache_ended = TTLCache(3600)  # 1 hour for long-ended events
top_players_cache = TTLCache(60)
heatmap_cache = TTLCache(60)
MAX_CHART_POINTS_PER_SERIES = 300

# 热力图按服务器本地墙钟小时对齐（日服活动），与 LiveBoost 的 hourly 时速榜一致
HEATMAP_TIMEZONE = 'Asia/Tokyo'
HEATMAP_TZ = ZoneInfo(HEATMAP_TIMEZONE)
HEATMAP_DEFAULT_HOURS = 48
HEATMAP_MAX_HOURS = 96


def clear_event_query_cache():
    chart_cache.clear()
    chart_cache_ended.clear()
    top_players_cache.clear()
    heatmap_cache.clear()


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

    event = repo.get_event(event_id)
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    is_old_event = (
        event and event.end_at > 0
        and now_ms > event.end_at + 24 * 3600 * 1000
    )

    # Try pre-computed cache first — simple SELECT, no GROUP BY
    rows = repo.get_chart_data_cache(event_id, interval)

    if not rows:
        if is_old_event:
            # Cache wasn't built for this pruned event — return empty rather than
            # falling back to incomplete player_score_history data
            return {}

        # Fallback to live GROUP BY if cache is empty (not yet backfilled)
        bucket_ms = 3600000 if interval == '1h' else 900000
        rows = repo.get_chart_history_aggregated(event_id, bucket_ms)
        if not rows:
            # Final fallback to chart_points table
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

    # Use longer TTL cache for ended events
    if is_old_event:
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


# ---------------------------------------------------------------------------
# 48h 热力图
# 逻辑移植自 LiveBoost 的 computeHourlyActivity：按服务器本地墙钟小时对齐，
# ---------------------------------------------------------------------------


def _hour_floor(ts_ms):
    """ts 落在的本地墙钟小时序号（自 epoch 起算，按 Asia/Tokyo 对齐）。"""
    local = dt.datetime.fromtimestamp(ts_ms / 1000, HEATMAP_TZ)
    # 把墙钟时刻当作 UTC 解释，得到连续的「本地小时序号」
    wall_utc = dt.datetime(
        local.year, local.month, local.day, local.hour,
        tzinfo=dt.timezone.utc,
    )
    return int(wall_utc.timestamp()) // 3600


def _hour_to_utc_ms(hour_index):
    """东京墙钟小时序号 -> 该小时起始的真实 UTC 毫秒。

    前端据此把每个热力图格子换算成浏览器本地时区展示，与「时速曲线」图一致。
    """
    wall_utc = dt.datetime.fromtimestamp(hour_index * 3600, dt.timezone.utc)
    offset_ms = wall_utc.astimezone(HEATMAP_TZ).utcoffset().total_seconds() * 1000
    return int(wall_utc.timestamp()) * 1000 - offset_ms


def _heatmap_window(ref_now, hours):
    """返回热力图覆盖的 (最旧, 最新) 墙钟小时序号。"""
    newest = _hour_floor(ref_now)
    return newest - (hours - 1), newest


def compute_hourly_activity(history_rows, ref_now, hours):
    """统计每位玩家最近 hours 个小时的周回次数。

    history_rows: 升序的历史记录，含 .uid / .timestamp / .pt
    返回 uid -> list[int]，index 0 最旧、index hours-1 为最新小时。
    """
    oldest, newest = _heatmap_window(ref_now, hours)

    by_uid = defaultdict(list)
    for rec in history_rows:
        by_uid[rec.uid].append((rec.timestamp, rec.pt))

    result = {}
    for uid, pts in by_uid.items():
        pts.sort(key=lambda x: x[0])
        counts = [0] * hours
        # 以「历史最高 PT」为基线：Bestdori 数据回拨造成的下跌不重复计数，
        # 只有涨到新高才算一次活跃（否则 下跌-回升 会被误算成一次周回）
        peak_pt = pts[0][1]
        for cur_ts, cur_pt in pts[1:]:
            if cur_pt > peak_pt:
                h = _hour_floor(cur_ts)
                if oldest <= h <= newest:
                    counts[h - oldest] += 1
                peak_pt = cur_pt
        result[uid] = counts
    return result


def _empty_heatmap(hours):
    return {
        'timezone': HEATMAP_TIMEZONE,
        'hours': hours,
        'ref_ts': 0,
        'global_max': 0,
        'players': {},
    }


def get_heatmap(event_id, limit=10, hours=HEATMAP_DEFAULT_HOURS, event=None):
    """返回 top N 玩家的 48h 活跃热力图数据。"""
    hours = min(max(1, hours), HEATMAP_MAX_HOURS)
    cache_key = (str(event_id), limit, hours)
    cached = heatmap_cache.get(cache_key)
    if cached is not None:
        return cached

    top_scores = repo.get_top_scores(event_id, limit)
    if not top_scores:
        return heatmap_cache.set(cache_key, _empty_heatmap(hours))

    top_player_uids = [score.uid for score in top_scores]
    history_records = repo.get_history_for_uids(event_id, top_player_uids)
    if not history_records:
        return heatmap_cache.set(cache_key, _empty_heatmap(hours))

    if event is None:
        event = repo.get_event(event_id)
    event_end = event.end_at if event and event.end_at and event.end_at > 0 else None

    # 基准时刻：活动结束前的最新采样点。活动结束后数据可能仍延伸一段
    # （末尾采样点已不在活动期），须以活动结束时间为上限，否则 48h 窗口
    # 会被推到活动结束后的空档，热力图看起来全是空的。
    active_samples = [rec.timestamp for rec in history_records
                      if event_end is None or rec.timestamp <= event_end]
    ref_now = max(active_samples) if active_samples else max(rec.timestamp for rec in history_records)

    # 丢弃基准时刻之后的残留采样：这些点虽不在窗口内，但会与基准落在同一
    # 墙钟小时，若不剔除会让最新一格多算
    history_records = [rec for rec in history_records if rec.timestamp <= ref_now]

    counts_by_uid = compute_hourly_activity(history_records, ref_now, hours)

    # 只统计当前展示玩家的最大值做颜色归一化，避免榜外爆肝玩家拉高 global_max
    global_max = 0
    for counts in counts_by_uid.values():
        if counts:
            global_max = max(global_max, max(counts))

    newest = _heatmap_window(ref_now, hours)[1]
    ref_ts = _hour_to_utc_ms(newest)  # 最新格子的起始 UTC 时刻

    players = {
        uid: {'counts': counts_by_uid.get(uid, [0] * hours)}
        for uid in top_player_uids
    }

    return heatmap_cache.set(cache_key, {
        'timezone': HEATMAP_TIMEZONE,
        'hours': hours,
        'ref_ts': ref_ts,
        'global_max': global_max,
        'players': players,
    })
