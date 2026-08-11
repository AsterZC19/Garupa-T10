# backend/services/monthly_query_service.py
"""月榜查询服务：top 玩家 / 曲线 / 热力图。逻辑与 event_query_service 对齐，
数据源为月榜专用表（monthly_scores / monthly_chart_points / monthly_heatmap_cache）。
"""
from collections import defaultdict

from services import monthly_repository as repo
from services.event_query_service import (
    _downsample_points,
    find_closest_point,
    find_last_point_before,
    row_pt,
    row_timestamp,
)
from services.heatmap_time import (
    HEATMAP_DEFAULT_HOURS,
    HEATMAP_MAX_HOURS,
    _empty_heatmap,
    build_heatmap_response,
)
from services.timeutil import now_ms
from services.ttl_cache import TTLCache

top_players_cache = TTLCache(60)
chart_cache = TTLCache(120)
heatmap_cache = TTLCache(60)
MAX_CHART_POINTS_PER_SERIES = 300


def clear_monthly_query_cache():
    top_players_cache.clear()
    chart_cache.clear()
    heatmap_cache.clear()


def clear_monthly_heatmap_cache():
    """只清热力图内存缓存：热力图按需重算后，让下一次读取拿到新缓存。"""
    heatmap_cache.clear()


def get_top_players(monthly_id, limit=10):
    """月榜 top N：当前 PT + 上一整点时速/周回次数/平均PT（从逐次快照计算）。

    与活动榜的语义一致：以「上一整点」为窗口计算时速。
    """
    cache_key = ('top', int(monthly_id), limit)
    cached = top_players_cache.get(cache_key)
    if cached is not None:
        return cached

    period = repo.get_monthly(int(monthly_id))
    if not period:
        return None

    current_time_ms = now_ms()
    # end_at == 0 视为后端未提供结束时间，锚定到当前时刻（否则 end_ts=0、
    # start_ts=-3600000、is_new 恒为 True，导致时速永远为 0）。
    anchor_ts = current_time_ms if period.end_at == 0 or current_time_ms < period.end_at else period.end_at
    end_ts = (anchor_ts // 3600000) * 3600000
    start_ts = end_ts - 3600000
    is_new = period.start_at > start_ts

    top_scores = repo.get_monthly_top_scores(int(monthly_id), limit)
    if not top_scores:
        return []

    uids = [s.uid for s in top_scores]
    history = repo.get_monthly_history_for_uids(int(monthly_id), uids)
    by_uid = defaultdict(list)
    for record in history:
        by_uid[record.uid].append(record)

    player_data = []
    for score in top_scores:
        player_history = by_uid[score.uid]
        hourly_speed = 0
        run_count = 0
        average_pt = 0

        if player_history and not is_new:
            start_point = find_closest_point(player_history, start_ts)
            end_point = find_closest_point(player_history, end_ts)
            if start_point and end_point and row_timestamp(start_point) < row_timestamp(end_point):
                time_diff_h = (row_timestamp(end_point) - row_timestamp(start_point)) / 3600000
                if time_diff_h > 0:
                    speed = (row_pt(end_point) - row_pt(start_point)) / time_diff_h
                    hourly_speed = round(speed) if speed > 0 else 0

            scores_in_hour = [r for r in player_history if start_ts <= row_timestamp(r) < end_ts]
            if scores_in_hour:
                last_before = find_last_point_before(player_history, start_ts)
                last_pt = row_pt(last_before) if last_before else row_pt(scores_in_hour[0])
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
            'rank': score.rank or 0,
            'signature': score.signature,
            'score_updated_at': score.updated_at,
            'hourly_speed': hourly_speed,
            'run_count': run_count if run_count > 0 else '-',
            'average_pt': average_pt if run_count > 0 else '-',
            'speed_rank': 0,
        })

    player_data.sort(key=lambda p: p['hourly_speed'], reverse=True)
    for index, player in enumerate(player_data):
        player['speed_rank'] = index + 1
    player_data.sort(key=lambda p: p['rank'])
    return top_players_cache.set(cache_key, player_data)


def get_chart_series(monthly_id, interval='15m'):
    """月榜 top 玩家 PT 曲线（预聚合 + 降采样）。interval: '15m' | '1h'。"""
    cache_key = ('chart', int(monthly_id), interval)
    cached = chart_cache.get(cache_key)
    if cached is not None:
        return cached

    bucket_ms = 3600000 if interval == '1h' else 900000
    rows = repo.get_monthly_chart_points_aggregated(int(monthly_id), bucket_ms)
    if not rows:
        return {}

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
    return chart_cache.set(cache_key, series)


def get_heatmap(monthly_id, limit=10, hours=HEATMAP_DEFAULT_HOURS, uids=None):
    """月榜 top N 玩家的 48h 活跃热力图（读 monthly_heatmap_cache）。

    时间换算与响应组装与活动榜共用 services/heatmap_time.build_heatmap_response；
    结构与活动榜一致：players[uid].counts 数组 index 0 最旧，ref_ts 为最新格子起始 UTC ms。
    """
    hours = min(max(1, hours), HEATMAP_MAX_HOURS)
    uid_key = tuple(sorted(str(u) for u in uids)) if uids else None
    cache_key = ('heat', int(monthly_id), limit, hours, uid_key)
    cached = heatmap_cache.get(cache_key)
    if cached is not None:
        return cached

    period = repo.get_monthly(int(monthly_id))
    if not period:
        return _empty_heatmap(hours)

    if uids:
        target_uids = [str(u) for u in uids]
    else:
        target_uids = [str(s.uid) for s in repo.get_monthly_top_scores(int(monthly_id), limit)]

    rows = repo.get_monthly_heatmap_cache_rows(int(monthly_id))
    if not rows:
        return _empty_heatmap(hours)

    return heatmap_cache.set(cache_key, build_heatmap_response(rows, target_uids, hours))
