# backend/services/heatmap.py
"""48h 热力图缓存：从 Bestdori 拉逐分钟榜单 → 按东京墙钟小时统计活跃度 → 落库。

页面请求热力图时直接读 event_heatmap_cache 表（见 event_query_service.get_heatmap），
不再每次实时请求 Bestdori。调度器每小时调用 compute_heatmap_cache 刷新：
- 进行中的活动每次都会重算（数据在变）；
- 已结束的活动只在缓存尚未覆盖到活动结束小时时算一次（数据已冻结）。
"""
import json
from collections import defaultdict

from services import event_repository as repo
from services.bestdori_client import client
from services.heatmap_time import (
    HEATMAP_MAX_HOURS,
    _activity_counts_by_uid,
    _heatmap_window,
    _hour_to_utc_ms,
    covers_window,
)
from services.timeutil import now_ms

TOP_UID_COUNT = 10  # 只缓存前 N 名玩家的热力图


def compute_heatmap_cache(event_id, hours=HEATMAP_MAX_HOURS):
    """预计算某活动 top-10 的热力图计数并落库。

    与旧的实时计算逻辑一致：取 /eventtop/data?interval=60000 的逐分钟采样点，
    按东京墙钟小时统计每位玩家「PT 创下新高」的次数。返回写入的玩家数，
    无数据 / 失败时返回 None。
    """
    event_id = str(event_id)
    top_json = client.get_event_top_data(event_id, server='jp', interval=60000)
    points = top_json.get('points', []) if top_json else []
    if not points:
        return None

    event = repo.get_event(event_id)
    event_end = event.end_at if event and event.end_at and event.end_at > 0 else None

    # 按 uid 聚合采样点，并记下每个 uid 的最新 PT（用于选前 N 名）
    pts_by_uid = defaultdict(list)
    latest_pt = {}
    for p in points:
        uid = str(p.get('uid'))
        ts = int(p['time'])
        val = int(p['value'])
        pts_by_uid[uid].append((ts, val))
        if uid not in latest_pt or ts > latest_pt[uid][0]:
            latest_pt[uid] = (ts, val)

    # 基准时刻：最新采样点。已结束活动按 end_at 封顶
    ref_now = max(v[0] for v in latest_pt.values())
    if event_end is not None and ref_now > event_end:
        ref_now = event_end

    counts_by_uid = _activity_counts_by_uid(pts_by_uid, ref_now, hours)
    if not counts_by_uid:
        return None

    target_uids = [
        uid for uid, _ in sorted(latest_pt.items(), key=lambda kv: kv[1][1], reverse=True)[:TOP_UID_COUNT]
    ]

    newest = _heatmap_window(ref_now, hours)[1]
    ref_ts = _hour_to_utc_ms(newest)

    rows = []
    for uid in target_uids:
        counts = counts_by_uid.get(uid)
        if counts is None:
            continue
        rows.append((uid, json.dumps(counts), ref_ts))

    if not rows:
        return None

    repo.replace_heatmap_cache(event_id, rows)
    return len(rows)


def heatmap_cache_covers_window(event_id, end_at_ms):
    """该活动已有缓存是否已覆盖到结束小时（用于已结束活动只算一次）。"""
    latest_ref_ts = repo.get_heatmap_cache_latest_ref_ts(event_id)
    return covers_window(latest_ref_ts, end_at_ms)


def compute_event_heatmap_cache_from_db(event_id, hours=HEATMAP_MAX_HOURS):
    """从本地 PlayerScoreHistory（逐分钟快照）重算活动热力图缓存并落库。

    与 compute_heatmap_cache（请求 Bestdori）等价，但只读本地库、不请求外部，
    供进行中活动的页面按需刷新使用。返回写入的玩家数；无数据返回 None。

    只读「窗口 + 基线缓冲」而不是全量历史：活动期间 PT 单调递增，窗口前一小段
    就足以建立「历史最高」基线，可把按需重算的读取量从几十万行降到几万行。
    """
    event_id = str(event_id)
    event = repo.get_event(event_id)
    if not event:
        return None

    ref_upper = now_ms()
    if event.end_at and event.end_at > 0:
        ref_upper = min(ref_upper, event.end_at)
    start_ts = ref_upper - (hours + 4) * 3600000  # 4 小时基线缓冲

    rows = repo.get_chart_history(event_id, start_ts=start_ts)
    if not rows:
        return None

    pts_by_uid = defaultdict(list)
    latest_pt = {}
    for row in rows:
        uid = str(row.uid)
        ts = int(row.timestamp)
        val = int(row.pt)
        pts_by_uid[uid].append((ts, val))
        if uid not in latest_pt or ts > latest_pt[uid][0]:
            latest_pt[uid] = (ts, val)

    ref_now = max(v[0] for v in latest_pt.values())
    if event.end_at and event.end_at > 0 and ref_now > event.end_at:
        ref_now = event.end_at

    counts_by_uid = _activity_counts_by_uid(pts_by_uid, ref_now, hours)
    if not counts_by_uid:
        return None

    target_uids = [
        uid for uid, _ in sorted(latest_pt.items(), key=lambda kv: kv[1][1], reverse=True)[:TOP_UID_COUNT]
    ]

    newest = _heatmap_window(ref_now, hours)[1]
    ref_ts = _hour_to_utc_ms(newest)

    cache_rows = []
    for uid in target_uids:
        counts = counts_by_uid.get(uid)
        if counts is None:
            continue
        cache_rows.append((uid, json.dumps(counts), ref_ts))

    if not cache_rows:
        return None

    repo.replace_heatmap_cache(event_id, cache_rows)
    return len(cache_rows)
