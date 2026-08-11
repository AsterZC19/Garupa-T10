# backend/services/heatmap_time.py
"""热力图的时间换算与共享组装。

热力图按服务器本地墙钟小时（Asia/Tokyo）对齐，与 LiveBoost 的 hourly 时速榜一致。
事件榜与月榜共用同一套「近 N 小时」窗口、格子起始时刻（ref_ts）与逐格活跃计数
逻辑，统一从这里取，避免时间处理分散/重复。

时间模型（前后端一致）：
- counts 数组 index 0 最旧、末尾最新，长度 = 小时数；
- ref_ts 为最新格子的起始 UTC 毫秒，前端据此换算成浏览器本地时区展示；
- hours 为最近 N 个东京墙钟小时（默认 48）。
"""
import datetime as dt
import json
from collections import defaultdict
from zoneinfo import ZoneInfo

HEATMAP_TIMEZONE = 'Asia/Tokyo'
HEATMAP_TZ = ZoneInfo(HEATMAP_TIMEZONE)
HEATMAP_DEFAULT_HOURS = 48
HEATMAP_MAX_HOURS = 96
HOUR_MS = 3600000


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
    return int(int(wall_utc.timestamp()) * 1000 - offset_ms)


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
        # 只保留基准时刻前的采样：活动结束后仍会追踪一段冻结榜单，
        # 剔除它们以免把窗口推后、或让最后一格多算
        pts = [p for p in pts if p[0] <= ref_now]
        if not pts:
            continue
        pts.sort(key=lambda x: x[0])
        counts = [0] * hours
        # 以「历史最高 PT」为基线：数据回拨造成的下跌不重复计数，
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


def covers_window(latest_ref_ts, end_at_ms):
    """已有缓存（最新格子 ref_ts）是否已覆盖到结束小时（用于已结束榜单只算一次）。"""
    if latest_ref_ts is None:
        return False
    return latest_ref_ts >= _hour_to_utc_ms(_hour_floor(end_at_ms))


def _parse_counts(counts_json):
    if not counts_json:
        return None
    try:
        parsed = json.loads(counts_json)
        if isinstance(parsed, list):
            return [int(c) for c in parsed]
    except Exception:
        return None
    return None


def _empty_heatmap(hours):
    return {
        'timezone': HEATMAP_TIMEZONE,
        'hours': hours,
        'ref_ts': 0,
        'global_max': 0,
        'players': {},
    }


def build_heatmap_response(rows, target_uids, hours):
    """把缓存行 [(uid, counts_json, ref_ts)] 组装成热力图响应。

    只统计目标玩家（与前端展示行一致），避免榜外爆肝玩家拉高 global_max。
    """
    stored = {}
    ref_ts = 0
    for uid, counts_json, row_ref_ts in rows:
        counts = _parse_counts(counts_json)
        if counts is None:
            continue
        stored[uid] = counts
        if row_ref_ts and row_ref_ts > ref_ts:
            ref_ts = row_ref_ts

    global_max = 0
    players = {}
    for uid in target_uids:
        counts = stored.get(uid)
        if counts is None:
            continue
        counts = counts[-hours:]  # 缓存覆盖整段窗口，取最后 hours 格
        players[uid] = {'counts': counts}
        global_max = max(global_max, max(counts))

    return {
        'timezone': HEATMAP_TIMEZONE,
        'hours': hours,
        'ref_ts': ref_ts,
        'global_max': global_max,
        'players': players,
    }
