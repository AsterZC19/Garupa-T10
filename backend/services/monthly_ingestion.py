# backend/services/monthly_ingestion.py
"""月榜数据摄取：从 GarupaSpeedTracker 后端拉取月榜期与 top 榜单，落库。

- master list（tracker info.json）→ MonthlyRanking（每期元信息，含 Bestdori 头图）
- top 快照（tracker top.json）→ 全量替换 MonthlyScore + 增量追加 MonthlyChartPoint
  （曲线与热力图数据源）

tracker 后端已持有官方 API 的设备签名，我们这边无需再连官方接口。
"""
import time

from services import tracker_client, monthly_repository as repo
from services.tracker_client import TrackerError

BESTDORI = "https://bestdori.com"
# 月榜头图：Bestdori 资源探索器路径 jp/event/{asset}/images 下的 logo.png
# （banner.png 在所有月份都是同一张占位图，logo.png 才是各月专属月榜图）
MONTHLY_BANNER_PATH = "/assets/jp/event/{asset}/images_rip/logo.png"


def resolve_banner_url(asset_bundle_name):
    if not asset_bundle_name:
        return None
    return f"{BESTDORI}{MONTHLY_BANNER_PATH.format(asset=asset_bundle_name)}"


def _server_value(arr, index=0):
    """tracker info 的字段多为 5 元素服务器数组，取第 index 个（默认 0=日服）。"""
    if not arr:
        return None
    if isinstance(arr, list):
        val = arr[index] if index < len(arr) else arr[0]
        return val
    return arr


def ingest_monthly_master_list():
    """从 tracker info.json 拉取全部月榜期并 upsert。返回期数。"""
    data = tracker_client.get_monthly_info()
    count = 0
    for mid_str, meta in (data or {}).items():
        try:
            mid = int(mid_str)
        except (TypeError, ValueError):
            continue
        if not isinstance(meta, dict):
            continue
        repo.upsert_monthly(
            monthly_id=mid,
            name=_server_value(meta.get('monthlyRankingName')) or f'月度 {mid}',
            start_at=int(_server_value(meta.get('startAt')) or 0),
            end_at=int(_server_value(meta.get('endAt')) or 0),
            banner_url=resolve_banner_url(meta.get('assetBundleName')),
            description=None,
        )
        count += 1
    return count


def _user_name_map(users):
    return {str(u.get('uid')): (u.get('name') or '') for u in (users or []) if u.get('uid')}


def _latest_scores_from_snapshot(monthly_id, points, users):
    """从 top 快照推导当前 top 分数。

    points: [{time, uid, value}]；users: [{uid, name, introduction, rank, ...}]
    取每位玩家最新一点的 value 作为当前 PT。
    """
    user_map = {}
    for u in users:
        uid = str(u.get('uid'))
        if uid:
            user_map[uid] = u

    latest_by_uid = {}
    for p in points:
        uid = str(p.get('uid'))
        ts = int(p.get('time') or p.get('timestamp') or 0)
        val = int(p.get('value') or 0)
        if uid not in latest_by_uid or ts > latest_by_uid[uid][0]:
            latest_by_uid[uid] = (ts, val)

    now_ts = int(time.time() * 1000)
    rows = []
    for uid, (ts, pt) in latest_by_uid.items():
        u = user_map.get(uid, {})
        rows.append({
            'monthly_id': monthly_id,
            'uid': uid,
            'name': u.get('name') or '',
            'pt': pt,
            'rank': 0,   # 位次由 PT 排序决定（tracker users 的 rank 字段不可靠）
            'signature': u.get('introduction') or '',
            'degree_id': None,
            'updated_at': ts or now_ts,
        })
    # 按 PT 倒序定 T10 位次
    rows.sort(key=lambda r: r['pt'], reverse=True)
    for i, r in enumerate(rows, start=1):
        r['rank'] = i
    return rows


def refresh_monthly_top(monthly_id):
    """拉取某期月榜的 top 快照并落库。

    - 全量替换 MonthlyScore（当前 top 快照）
    - 增量追加 MonthlyChartPoint（仅新时间戳，去重）
    返回写入的新快照点数；失败返回 0。
    """
    monthly_id = int(monthly_id)
    try:
        snapshot = tracker_client.get_monthly_top(monthly_id)
    except TrackerError as e:
        print(f"[monthly_ingestion] monthly={monthly_id} skipped: {e}")
        return 0

    points = snapshot.get('points') or []
    users = snapshot.get('users') or []
    if not points:
        return 0

    # --- 最新 top 快照 ---
    score_rows = _latest_scores_from_snapshot(monthly_id, points, users)
    if score_rows:
        repo.replace_monthly_scores(monthly_id, score_rows)

    # --- 增量追加曲线点（仅新时间戳，去重） ---
    last_ts = repo.get_monthly_last_stored_ts(monthly_id)
    name_map = _user_name_map(users)
    new_points = []
    for p in points:
        ts = int(p.get('time') or p.get('timestamp') or 0)
        if ts <= last_ts:
            continue
        uid = str(p.get('uid'))
        new_points.append({
            'uid': uid,
            'name': name_map.get(uid, ''),
            'timestamp': ts,
            'pt': int(p.get('value') or 0),
        })
    if not new_points:
        return 0
    return repo.append_monthly_chart_points_if_missing(monthly_id, new_points)


def backfill_monthly_history(monthly_id):
    """回填某期月榜的全部历史点（含最新快照）。返回新增点数。"""
    monthly_id = int(monthly_id)
    try:
        snapshot = tracker_client.get_monthly_top(monthly_id, force=True)
    except TrackerError as e:
        print(f"[monthly_ingestion] monthly={monthly_id} backfill skipped: {e}")
        return 0

    points = snapshot.get('points') or []
    users = snapshot.get('users') or []
    if not points:
        return 0

    score_rows = _latest_scores_from_snapshot(monthly_id, points, users)
    if score_rows:
        repo.replace_monthly_scores(monthly_id, score_rows)

    name_map = _user_name_map(users)
    rows = [{
        'uid': str(p.get('uid')),
        'name': name_map.get(str(p.get('uid')), ''),
        'timestamp': int(p.get('time') or p.get('timestamp') or 0),
        'pt': int(p.get('value') or 0),
    } for p in points if p.get('time') or p.get('timestamp')]
    return repo.append_monthly_chart_points_if_missing(monthly_id, rows)


def record_active_monthly_top():
    """刷新当前进行中的月榜。返回写入点数（无进行中月榜返回 0）。"""
    current = repo.get_current_or_latest_monthly()
    if not current:
        return 0
    now_ms = int(time.time() * 1000)
    if current.start_at > now_ms:  # 尚未开始
        return 0
    return refresh_monthly_top(current.monthly_id)
