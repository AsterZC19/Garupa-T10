# backend/services/monthly_heatmap.py
"""月榜热力图缓存：从 monthly_chart_points 的逐次快照计算「PT 创下新高」次数并落库。

与活动榜热力图（services/heatmap.py）逻辑一致，只是数据源不同：
- 活动榜：调度器每小时从 Bestdori 拉逐分钟榜单计算；
- 月榜：官方 API 只提供当前 top 快照，调度器每分钟落一条快照到
  monthly_chart_points，这里直接读这些快照统计即可。
"""
import json
from collections import defaultdict

from services import monthly_repository as repo
from services.event_query_service import (
    HEATMAP_MAX_HOURS,
    _activity_counts_by_uid,
    _heatmap_window,
    _hour_floor,
    _hour_to_utc_ms,
)

TOP_UID_COUNT = 10


def compute_monthly_heatmap_cache(monthly_id, hours=HEATMAP_MAX_HOURS):
    """预计算某期月榜 top-N 玩家的热力图计数并落库。返回写入的玩家数。"""
    monthly_id = int(monthly_id)
    points = repo.get_monthly_chart_points(monthly_id)
    if not points:
        return None

    period = repo.get_monthly(monthly_id)
    event_end = period.end_at if period and period.end_at and period.end_at > 0 else None

    pts_by_uid = defaultdict(list)
    latest_pt = {}
    for p in points:
        uid = str(p.uid)
        pts_by_uid[uid].append((p.timestamp, p.pt))
        if uid not in latest_pt or p.timestamp > latest_pt[uid][0]:
            latest_pt[uid] = (p.timestamp, p.pt)

    ref_now = max(v[0] for v in latest_pt.values())
    if event_end is not None and ref_now > event_end:
        ref_now = event_end

    counts_by_uid = _activity_counts_by_uid(pts_by_uid, ref_now, hours)
    if not counts_by_uid:
        return None

    # 目标玩家：优先当前 top 快照（展示行一致），否则按最新 PT 取前 N
    target_uids = [str(s.uid) for s in repo.get_monthly_top_scores(monthly_id, TOP_UID_COUNT)]
    if not target_uids:
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

    repo.replace_monthly_heatmap_cache(monthly_id, rows)
    return len(rows)


def monthly_heatmap_cache_covers_window(monthly_id, end_at_ms):
    """缓存是否已覆盖到月榜结束小时（用于已结束月榜只算一次）。"""
    latest_ref_ts = repo.get_monthly_heatmap_latest_ref_ts(monthly_id)
    if latest_ref_ts is None:
        return False
    return latest_ref_ts >= _hour_to_utc_ms(_hour_floor(end_at_ms))
