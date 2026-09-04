"""Indexed history reads for hourly statistics, including nearest boundary points."""
from sqlalchemy import func, select, union_all

from models import db


def get_history_window(model, period_column, period_id, uids, start_ts, end_ts):
    # Keep the predecessor for run counts and both neighbours for nearest-point
    # speed. Never limit their distance: sparse/pruned histories keep their meaning.
    queries = []
    for uid in dict.fromkeys(uids):
        scope = (period_column == period_id, model.uid == uid)
        before = select(func.max(model.timestamp)).where(
            *scope, model.timestamp < start_ts
        ).scalar_subquery()
        after = select(func.min(model.timestamp)).where(
            *scope, model.timestamp > end_ts
        ).scalar_subquery()
        queries.append(select(model.uid, model.timestamp, model.pt).where(
            *scope,
            model.timestamp >= func.coalesce(before, start_ts),
            model.timestamp <= func.coalesce(after, end_ts),
        ))
    if not queries:
        return []
    # Bound SQL parameters/compound SELECT terms for callers requesting large lists.
    # Normal top-10 reads use one query and the existing composite index.
    rows = []
    for offset in range(0, len(queries), 50):
        rows.extend(db.session.execute(
            union_all(*queries[offset:offset + 50]).order_by('timestamp')
        ).all())
    if len(queries) > 50:
        rows.sort(key=lambda row: row.timestamp)
    return rows
