from datetime import datetime
from sqlalchemy import Integer, cast, func
from models import db, Event, Score, ChartPoint, PlayerScoreHistory


def now_ms():
    return int(datetime.utcnow().timestamp() * 1000)


def serialize_event(event):
    return {
        'event_id': event.event_id,
        'name': event.name,
        'type': event.event_type,
        'start_at': event.start_at,
        'end_at': event.end_at,
        'banner_url': event.banner_url,
        'description': event.description
    }


def list_events(limit=1000):
    return Event.query.order_by(Event.start_at.desc()).limit(limit).all()


def get_event(event_id):
    return Event.query.filter_by(event_id=str(event_id)).first()


def get_current_or_latest_event():
    current_time = now_ms()
    current = Event.query.filter(Event.start_at <= current_time, Event.end_at >= current_time).order_by(Event.start_at.desc()).first()
    if current:
        return current, True
    return Event.query.order_by(cast(Event.event_id, Integer).desc()).first(), False


def get_active_event():
    current_time = now_ms()
    return Event.query.filter(Event.start_at <= current_time, Event.end_at >= current_time).order_by(Event.start_at.desc()).first()


def get_all_event_ids():
    return {str(e.event_id) for e in Event.query.with_entities(Event.event_id).all()}


def get_event_ids_with_history():
    return {str(h.event_id) for h in PlayerScoreHistory.query.with_entities(PlayerScoreHistory.event_id).distinct().all()}


def upsert_event(event_id, name, event_type, start_at, end_at, banner_url=None, description=None):
    event = get_event(event_id)
    if not event:
        event = Event(
            event_id=str(event_id),
            name=name,
            event_type=event_type,
            start_at=start_at or 0,
            end_at=end_at or 0,
            banner_url=banner_url,
            description=description,
            updated_at=now_ms()
        )
        db.session.add(event)
    else:
        event.name = name
        event.event_type = event_type
        event.start_at = start_at or event.start_at
        event.end_at = end_at or event.end_at
        event.banner_url = banner_url or event.banner_url
        event.description = description or event.description
        event.updated_at = now_ms()
    db.session.commit()
    return event


def replace_scores(event_id, rows):
    event_id = str(event_id)
    # DELETE + bulk_insert is faster than row-by-row comparison in SQLite
    Score.query.filter_by(event_id=event_id).delete()
    if rows:
        db.session.bulk_insert_mappings(Score, rows)
    db.session.commit()


def chunked(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def append_chart_points_if_missing(event_id, points, chunk_size=400, min_timestamp=0):
    event_id = str(event_id)
    if not points:
        return 0

    # Filter to only process points newer than min_timestamp
    if min_timestamp:
        points = [p for p in points if p['timestamp'] >= min_timestamp]
        if not points:
            return 0

    tuples = [(str(point['uid']), point['timestamp']) for point in points]
    existing_points = []
    for chunk in chunked(tuples, chunk_size):
        existing_points.extend(ChartPoint.query.filter(
            ChartPoint.event_id == event_id,
            db.tuple_(ChartPoint.uid, ChartPoint.timestamp).in_(chunk)
        ).all())
    existing = {(point.uid, point.timestamp): point for point in existing_points}

    changed = 0
    to_add = []
    for point in points:
        key = (str(point['uid']), point['timestamp'])
        existing_point = existing.get(key)
        if existing_point:
            if existing_point.pt != point['pt'] or existing_point.name != point.get('name', ''):
                existing_point.pt = point['pt']
                existing_point.name = point.get('name', '')
                changed += 1
            continue

        new_point = ChartPoint(
            event_id=event_id,
            uid=key[0],
            name=point.get('name', ''),
            timestamp=point['timestamp'],
            pt=point['pt']
        )
        existing[key] = new_point
        to_add.append(new_point)

    if to_add:
        db.session.bulk_save_objects(to_add)
        changed += len(to_add)
    if changed:
        db.session.commit()
    return changed


def get_chart_data_cache(event_id, interval='15m'):
    """Read pre-computed chart data from cache table — simple SELECT, no GROUP BY."""
    try:
        from models import ChartDataCache
        rows = ChartDataCache.query.filter_by(
            event_id=str(event_id),
            bucket_interval=interval
        ).order_by(ChartDataCache.bucket_ts.asc()).all()
        return [(r.uid, r.name, r.bucket_ts, r.pt) for r in rows]
    except Exception:
        return []


def _update_chart_data_cache(event_id, changed_items):
    """Incrementally update chart_data_cache from newly inserted/updated history rows."""
    if not changed_items:
        return
    try:
        from models import ChartDataCache
    except Exception:
        return

    event_id = str(event_id)
    # Compute bucket entries for both intervals, keeping max pt per bucket
    buckets = {}  # (uid, interval, bucket_ts) -> {'pt': max_pt, 'name': name}
    for item in changed_items:
        uid = str(item['uid'])
        ts = item['timestamp']
        pt = item['pt']
        name = item.get('name') or uid

        for interval, bucket_ms in [('15m', 900000), ('1h', 3600000)]:
            bucket_ts = (ts // bucket_ms) * bucket_ms
            key = (uid, interval, bucket_ts)
            if key not in buckets or pt > buckets[key]['pt']:
                buckets[key] = {'pt': pt, 'name': name}

    # Fetch existing cache entries for the affected uids
    affected_uids = list({k[0] for k in buckets})
    try:
        existing_rows = ChartDataCache.query.filter(
            ChartDataCache.event_id == event_id,
            ChartDataCache.uid.in_(affected_uids)
        ).all()
        existing = {(r.uid, r.bucket_interval, r.bucket_ts): r for r in existing_rows}
    except Exception:
        existing = {}

    to_add = []
    for (uid, interval, bucket_ts), data in buckets.items():
        existing_row = existing.get((uid, interval, bucket_ts))
        if existing_row:
            if data['pt'] > existing_row.pt:
                try:
                    existing_row.pt = data['pt']
                    existing_row.name = data['name']
                except Exception:
                    pass
        else:
            to_add.append(ChartDataCache(
                event_id=event_id,
                uid=uid,
                bucket_interval=interval,
                bucket_ts=bucket_ts,
                pt=data['pt'],
                name=data['name']
            ))

    if to_add:
        try:
            db.session.bulk_save_objects(to_add)
        except Exception:
            pass


def backfill_chart_data_cache(event_id=None):
    """Backfill chart_data_cache from player_score_history. Runs GROUP BY once per event."""
    from models import ChartDataCache

    if event_id:
        events_to_process = [str(event_id)]
    else:
        events_to_process = sorted(get_event_ids_with_history())

    total = 0
    for eid in events_to_process:
        # Clear existing cache for this event
        ChartDataCache.query.filter_by(event_id=eid).delete()

        for interval, bucket_ms in [('15m', 900000), ('1h', 3600000)]:
            bucket_key = func.floor(PlayerScoreHistory.timestamp / bucket_ms).cast(Integer)
            rows = db.session.query(
                PlayerScoreHistory.uid,
                func.max(PlayerScoreHistory.name).label('name'),
                (bucket_key * bucket_ms).label('bucket_ts'),
                func.max(PlayerScoreHistory.pt).label('pt')
            ).filter_by(event_id=eid).group_by(
                PlayerScoreHistory.uid,
                bucket_key
            ).all()

            cache_rows = [
                ChartDataCache(
                    event_id=eid,
                    uid=r.uid,
                    bucket_interval=interval,
                    bucket_ts=r.bucket_ts,
                    pt=r.pt,
                    name=r.name or r.uid
                )
                for r in rows
            ]

            for chunk in chunked(cache_rows, 400):
                db.session.bulk_save_objects(chunk)
                total += len(chunk)

        db.session.commit()
        print(f"Backfilled cache for event {eid}")

    return total


def append_player_score_history_if_missing(event_id, rows, batch_size=2000, chunk_size=400, min_timestamp=0):
    if not rows:
        return 0

    event_id = str(event_id)
    # Filter to only process rows newer than min_timestamp (skip already-stored data)
    if min_timestamp:
        rows = [r for r in rows if r['timestamp'] >= min_timestamp]
        if not rows:
            return 0

    tuples = [(str(row['uid']), row['timestamp']) for row in rows]
    existing_points = []
    for chunk in chunked(tuples, chunk_size):
        existing_points.extend(PlayerScoreHistory.query.filter(
            PlayerScoreHistory.event_id == event_id,
            db.tuple_(PlayerScoreHistory.uid, PlayerScoreHistory.timestamp).in_(chunk)
        ).all())
    existing = {(point.uid, point.timestamp): point for point in existing_points}

    changed = 0
    changed_items = []
    batch = []
    for row in rows:
        key = (str(row['uid']), row['timestamp'])
        name = row.get('name') or key[0]
        existing_point = existing.get(key)
        if existing_point:
            if existing_point.pt != row['pt'] or existing_point.name != name:
                existing_point.pt = row['pt']
                existing_point.name = name
                changed += 1
                changed_items.append({'uid': key[0], 'timestamp': row['timestamp'], 'pt': row['pt'], 'name': name})
            continue

        new_point = PlayerScoreHistory(
            event_id=event_id,
            uid=key[0],
            name=name,
            pt=row['pt'],
            timestamp=row['timestamp']
        )
        existing[key] = new_point
        batch.append(new_point)
        changed_items.append({'uid': key[0], 'timestamp': row['timestamp'], 'pt': row['pt'], 'name': name})
        if len(batch) >= batch_size:
            db.session.bulk_save_objects(batch)
            changed += len(batch)
            batch = []

    if batch:
        db.session.bulk_save_objects(batch)
        changed += len(batch)

    # Incrementally update pre-computed chart cache from changed rows
    _update_chart_data_cache(event_id, changed_items)

    if changed:
        db.session.commit()
    return changed


def get_scores(event_id, limit):
    return Score.query.filter_by(event_id=str(event_id)).order_by(Score.rank.asc()).limit(limit).all()


def get_chart_history(event_id, start_ts=None, end_ts=None):
    query = PlayerScoreHistory.query.with_entities(
        PlayerScoreHistory.uid,
        PlayerScoreHistory.name,
        PlayerScoreHistory.timestamp,
        PlayerScoreHistory.pt
    ).filter_by(event_id=str(event_id))
    if start_ts is not None:
        query = query.filter(PlayerScoreHistory.timestamp >= start_ts)
    if end_ts is not None:
        query = query.filter(PlayerScoreHistory.timestamp <= end_ts)
    return query.order_by(PlayerScoreHistory.timestamp.asc()).all()


def get_chart_history_aggregated(event_id, bucket_ms):
    """Return chart data aggregated into time buckets in SQL, drastically reducing row count."""
    bucket_key = func.floor(PlayerScoreHistory.timestamp / bucket_ms).cast(Integer)
    return db.session.query(
        PlayerScoreHistory.uid,
        func.max(PlayerScoreHistory.name).label('name'),
        (bucket_key * bucket_ms).label('bucket_ts'),
        func.max(PlayerScoreHistory.pt).label('pt')
    ).filter_by(event_id=str(event_id)).group_by(
        PlayerScoreHistory.uid,
        bucket_key
    ).order_by('bucket_ts').all()


def get_chart_history_aggregated_fallback(event_id, bucket_ms):
    """Fallback: aggregate from chart_points table when player_score_history has no data."""
    bucket_key = func.floor(ChartPoint.timestamp / bucket_ms).cast(Integer)
    return db.session.query(
        ChartPoint.uid,
        func.max(ChartPoint.name).label('name'),
        (bucket_key * bucket_ms).label('bucket_ts'),
        func.max(ChartPoint.pt).label('pt')
    ).filter_by(event_id=str(event_id)).group_by(
        ChartPoint.uid,
        bucket_key
    ).order_by('bucket_ts').all()


def get_top_scores(event_id, limit):
    return Score.query.filter_by(event_id=str(event_id)).order_by(Score.pt.desc()).limit(limit).all()


def get_history_for_uids(event_id, uids):
    return PlayerScoreHistory.query.with_entities(
        PlayerScoreHistory.uid,
        PlayerScoreHistory.timestamp,
        PlayerScoreHistory.pt
    ).filter(
        PlayerScoreHistory.event_id == str(event_id),
        PlayerScoreHistory.uid.in_(uids)
    ).order_by(PlayerScoreHistory.timestamp.asc()).all()


def get_duplicate_history_points(limit=100):
    return db.session.query(
        PlayerScoreHistory.event_id,
        PlayerScoreHistory.uid,
        PlayerScoreHistory.timestamp,
        func.count(PlayerScoreHistory.id).label('count'),
        func.min(PlayerScoreHistory.id).label('keep_id')
    ).group_by(
        PlayerScoreHistory.event_id,
        PlayerScoreHistory.uid,
        PlayerScoreHistory.timestamp
    ).having(func.count(PlayerScoreHistory.id) > 1).limit(limit).all()


def count_duplicate_history_points():
    rows = db.session.query(
        func.count(PlayerScoreHistory.id).label('count')
    ).group_by(
        PlayerScoreHistory.event_id,
        PlayerScoreHistory.uid,
        PlayerScoreHistory.timestamp
    ).having(func.count(PlayerScoreHistory.id) > 1).all()
    return sum(row.count - 1 for row in rows)
