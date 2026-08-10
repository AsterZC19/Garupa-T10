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


def _activity_counts_by_uid(pts_by_uid, ref_now, hours):
    """按东京墙钟小时统计每位玩家「PT 创下新高」的次数（纯内存，不落库）。

    pts_by_uid: uid -> [(timestamp_ms, pt), ...]（无序，内部会排序）
    返回 uid -> list[int]，index 0 最旧、index hours-1 为最新小时。
    """
    oldest, newest = _heatmap_window(ref_now, hours)
    result = {}
    for uid, pts in pts_by_uid.items():
        # 只保留基准时刻前的采样：活动结束后 Bestdori 仍会追踪一段冻结榜单，
        # 剔除它们以免把窗口推后、或让最后一格多算
        pts = [p for p in pts if p[0] <= ref_now]
        if not pts:
            continue
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


def get_heatmap_live(event_id, limit=10, hours=HEATMAP_DEFAULT_HOURS, uids=None):
    """返回 top N 玩家的 48h 活跃热力图数据。

    与 LiveBoost 一致：直接调用 Bestdori /eventtop/data?interval=60000 拿逐分钟
    采样点，在内存里按东京墙钟小时统计活跃度，不落库——不受 player_score_history
    清理影响，也无需为热力图保留任何历史数据（节省硬盘）。

    uids: 可选。前端把「表格正在展示」的玩家 uid 列表传进来时，只返回这些玩家的
    热力图并据此归一化颜色，保证与页面展示行一致；未传则退回按最新 PT 取前 limit 名。
    """
    from services.bestdori_client import client

    hours = min(max(1, hours), HEATMAP_MAX_HOURS)
    uid_key = tuple(sorted(str(u) for u in uids)) if uids else None
    cache_key = ('live', str(event_id), limit, hours, uid_key)
    cached = heatmap_cache.get(cache_key)
    if cached is not None:
        return cached

    top_json = client.get_event_top_data(event_id, server='jp', interval=60000)
    points = top_json.get('points', []) if top_json else []
    if not points:
        return heatmap_cache.set(cache_key, _empty_heatmap(hours))

    event = repo.get_event(event_id)
    event_end = event.end_at if event and event.end_at and event.end_at > 0 else None

    # 按 uid 聚合采样点，并记下每个 uid 的最新 PT
    pts_by_uid = defaultdict(list)
    latest_pt = {}
    for p in points:
        uid = str(p.get('uid'))
        ts = int(p['time'])
        val = int(p['value'])
        pts_by_uid[uid].append((ts, val))
        if uid not in latest_pt or ts > latest_pt[uid][0]:
            latest_pt[uid] = (ts, val)

    # 基准时刻：数据中最新采样点。已结束活动按 end_at 封顶，避免活动结束后
    # 榜单仍被追踪的空档把 48h 窗口推后、看起来全是空的
    ref_now = max(v[0] for v in latest_pt.values())
    if event_end is not None and ref_now > event_end:
        ref_now = event_end

    counts_by_uid = _activity_counts_by_uid(pts_by_uid, ref_now, hours)
    if not counts_by_uid:
        return heatmap_cache.set(cache_key, _empty_heatmap(hours))

    # 目标玩家 = 前端展示的那批 uid；未传时退回按最新 PT 取榜单前 limit 名
    if uids:
        target_uids = [str(u) for u in uids]
    else:
        target_uids = [uid for uid, _ in sorted(latest_pt.items(), key=lambda kv: kv[1][1], reverse=True)[:limit]]

    # 颜色归一化只按目标玩家统计，避免榜外爆肝玩家拉高 global_max
    global_max = 0
    players = {}
    for uid in target_uids:
        counts = counts_by_uid.get(uid)
        if counts:
            players[uid] = {'counts': counts}
            global_max = max(global_max, max(counts))

    newest = _heatmap_window(ref_now, hours)[1]
    ref_ts = _hour_to_utc_ms(newest)  # 最新格子的起始 UTC 时刻

    return heatmap_cache.set(cache_key, {
        'timezone': HEATMAP_TIMEZONE,
        'hours': hours,
        'ref_ts': ref_ts,
        'global_max': global_max,
        'players': players,
    })
