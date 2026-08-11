# backend/services/monthly_repository.py
"""月榜数据仓库层：SQLite 读写（对应 event_repository.py 的月榜版本）。"""
import json

from sqlalchemy import func
from sqlalchemy import Integer, cast
from models import db, MonthlyRanking, MonthlyScore, MonthlyChartPoint, MonthlyHeatmapCache
from services.timeutil import now_ms


def serialize_monthly(period):
    return {
        'monthly_id': period.monthly_id,
        'name': period.name,
        'start_at': period.start_at,
        'end_at': period.end_at,
        'banner_url': period.banner_url,
        'description': period.description,
    }


def list_monthly(limit=500):
    return MonthlyRanking.query.order_by(MonthlyRanking.monthly_id.desc()).limit(limit).all()


def get_monthly(monthly_id):
    return MonthlyRanking.query.filter_by(monthly_id=int(monthly_id)).first()


def get_current_or_latest_monthly():
    now = now_ms()
    # end_at == 0 视为后端未提供结束时间（按进行中处理）
    current = MonthlyRanking.query.filter(
        MonthlyRanking.start_at <= now,
        (MonthlyRanking.end_at == 0) | (MonthlyRanking.end_at >= now),
    ).order_by(MonthlyRanking.monthly_id.desc()).first()
    if current:
        return current
    return MonthlyRanking.query.order_by(MonthlyRanking.monthly_id.desc()).first()


def is_monthly_period_active(period, now_ts=None):
    """月榜是否进行中。end_at == 0 视为后端未提供结束时间，按进行中处理。"""
    if period is None:
        return False
    now = now_ts if now_ts is not None else now_ms()
    if period.start_at and period.start_at > now:
        return False
    return period.end_at == 0 or now <= period.end_at


def count_monthly():
    return MonthlyRanking.query.count()


def upsert_monthly(monthly_id, name, start_at, end_at, banner_url=None, description=None):
    monthly_id = int(monthly_id)
    period = get_monthly(monthly_id)
    if not period:
        period = MonthlyRanking(
            monthly_id=monthly_id,
            name=name,
            start_at=start_at or 0,
            end_at=end_at or 0,
            banner_url=banner_url,
            description=description,
            updated_at=now_ms(),
        )
        db.session.add(period)
    else:
        period.name = name or period.name
        period.start_at = start_at or period.start_at
        period.end_at = end_at or period.end_at
        period.banner_url = banner_url or period.banner_url
        period.description = description or period.description
        period.updated_at = now_ms()
    db.session.commit()
    return period


def replace_monthly_scores(monthly_id, rows):
    """全量替换某期月榜的 top 快照。rows: [dict(uid, name, pt, rank, signature, degree_id, updated_at)]"""
    monthly_id = int(monthly_id)
    MonthlyScore.query.filter_by(monthly_id=monthly_id).delete()
    if rows:
        db.session.bulk_insert_mappings(MonthlyScore, rows)
    db.session.commit()


def get_monthly_top_scores(monthly_id, limit=10):
    return MonthlyScore.query.filter_by(monthly_id=int(monthly_id)).order_by(
        MonthlyScore.pt.desc()
    ).limit(limit).all()


def get_monthly_scores(monthly_id):
    return MonthlyScore.query.filter_by(monthly_id=int(monthly_id)).order_by(
        MonthlyScore.rank.asc()
    ).all()


def chunked(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def append_monthly_chart_points_if_missing(monthly_id, points, chunk_size=400):
    """追加月榜逐次快照，按 (monthly_id, uid, timestamp) 去重；已存在的更新 pt/name。"""
    monthly_id = int(monthly_id)
    if not points:
        return 0
    tuples = [(str(p['uid']), p['timestamp']) for p in points]
    existing_points = []
    for chunk in chunked(tuples, chunk_size):
        existing_points.extend(MonthlyChartPoint.query.filter(
            MonthlyChartPoint.monthly_id == monthly_id,
            db.tuple_(MonthlyChartPoint.uid, MonthlyChartPoint.timestamp).in_(chunk),
        ).all())
    existing = {(p.uid, p.timestamp): p for p in existing_points}

    changed = 0
    to_add = []
    for p in points:
        key = (str(p['uid']), p['timestamp'])
        row = existing.get(key)
        if row:
            if row.pt != p['pt'] or row.name != p.get('name', ''):
                row.pt = p['pt']
                row.name = p.get('name', '')
                changed += 1
            continue
        new_point = MonthlyChartPoint(
            monthly_id=monthly_id,
            uid=key[0],
            name=p.get('name', ''),
            timestamp=p['timestamp'],
            pt=p['pt'],
        )
        existing[key] = new_point
        to_add.append(new_point)

    if to_add:
        db.session.bulk_save_objects(to_add)
        changed += len(to_add)
    if changed:
        db.session.commit()
    return changed


def get_monthly_chart_points(monthly_id, start_ts=None, end_ts=None):
    query = MonthlyChartPoint.query.with_entities(
        MonthlyChartPoint.uid,
        MonthlyChartPoint.name,
        MonthlyChartPoint.timestamp,
        MonthlyChartPoint.pt,
    ).filter_by(monthly_id=int(monthly_id))
    if start_ts is not None:
        query = query.filter(MonthlyChartPoint.timestamp >= start_ts)
    if end_ts is not None:
        query = query.filter(MonthlyChartPoint.timestamp <= end_ts)
    return query.order_by(MonthlyChartPoint.timestamp.asc()).all()


def get_monthly_chart_points_aggregated(monthly_id, bucket_ms):
    bucket_key = func.floor(MonthlyChartPoint.timestamp / bucket_ms).cast(Integer)
    return db.session.query(
        MonthlyChartPoint.uid,
        func.max(MonthlyChartPoint.name).label('name'),
        (bucket_key * bucket_ms).label('bucket_ts'),
        func.max(MonthlyChartPoint.pt).label('pt'),
    ).filter_by(monthly_id=int(monthly_id)).group_by(
        MonthlyChartPoint.uid, bucket_key
    ).order_by('bucket_ts').all()


def get_monthly_history_for_uids(monthly_id, uids):
    return MonthlyChartPoint.query.with_entities(
        MonthlyChartPoint.uid,
        MonthlyChartPoint.timestamp,
        MonthlyChartPoint.pt,
    ).filter(
        MonthlyChartPoint.monthly_id == int(monthly_id),
        MonthlyChartPoint.uid.in_(uids),
    ).order_by(MonthlyChartPoint.timestamp.asc()).all()


def get_monthly_last_stored_ts(monthly_id):
    """该期月榜已存储的最大快照时间戳；无数据返回 0。"""
    row = db.session.query(func.max(MonthlyChartPoint.timestamp)).filter_by(
        monthly_id=int(monthly_id)
    ).first()
    return row[0] or 0 if row else 0


def get_monthly_last_stored_ts_by_uid(monthly_id):
    """各 uid 已存储的最大快照时间戳，返回 {uid: max_ts}。

    用于增量刷新时按玩家各自的时间戳过滤，避免用全局 max 把新进榜玩家
    进榜前的历史点一并丢弃。
    """
    rows = db.session.query(
        MonthlyChartPoint.uid,
        func.max(MonthlyChartPoint.timestamp),
    ).filter_by(monthly_id=int(monthly_id)).group_by(MonthlyChartPoint.uid).all()
    return {uid: (ts or 0) for uid, ts in rows}


def replace_monthly_heatmap_cache(monthly_id, rows):
    monthly_id = int(monthly_id)
    MonthlyHeatmapCache.query.filter_by(monthly_id=monthly_id).delete()
    if rows:
        now = now_ms()
        db.session.bulk_insert_mappings(MonthlyHeatmapCache, [
            {'monthly_id': monthly_id, 'uid': uid, 'counts': counts, 'ref_ts': ref_ts, 'updated_at': now}
            for uid, counts, ref_ts in rows
        ])
    db.session.commit()


def get_monthly_heatmap_cache_rows(monthly_id):
    try:
        rows = MonthlyHeatmapCache.query.filter_by(monthly_id=int(monthly_id)).all()
        return [(r.uid, r.counts, r.ref_ts) for r in rows]
    except Exception:
        return []


def get_monthly_heatmap_latest_ref_ts(monthly_id):
    try:
        row = MonthlyHeatmapCache.query.filter_by(monthly_id=int(monthly_id)).order_by(
            MonthlyHeatmapCache.ref_ts.desc()
        ).first()
        return row.ref_ts if row else None
    except Exception:
        return None


def delete_monthly_data(monthly_id):
    """清理某期月榜的全部本地数据（调试用）。"""
    monthly_id = int(monthly_id)
    MonthlyScore.query.filter_by(monthly_id=monthly_id).delete()
    MonthlyChartPoint.query.filter_by(monthly_id=monthly_id).delete()
    MonthlyHeatmapCache.query.filter_by(monthly_id=monthly_id).delete()
    db.session.commit()
