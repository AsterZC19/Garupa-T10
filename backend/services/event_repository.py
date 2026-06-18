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


def list_events(limit=100):
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
    existing = {s.uid: s for s in Score.query.filter_by(event_id=event_id).all()}

    new_by_uid = {str(r['uid']): r for r in rows}
    new_uids = set(new_by_uid.keys())
    existing_uids = set(existing.keys())

    # Check if anything actually changed
    if new_uids == existing_uids:
        all_same = True
        for uid, s in existing.items():
            r = new_by_uid[uid]
            if (s.pt != int(r.get('pt', 0)) or
                s.rank != int(r.get('rank', 0)) or
                s.name != str(r.get('name', '')) or
                s.signature != str(r.get('signature', ''))):
                all_same = False
                break
        if all_same:
            return  # No changes, skip delete+insert

    # Delete removed uids
    removed = existing_uids - new_uids
    if removed:
        Score.query.filter(Score.event_id == event_id, Score.uid.in_(removed)).delete(synchronize_session=False)

    # Upsert: update existing, insert new
    for r in rows:
        uid = str(r['uid'])
        if uid in existing:
            s = existing[uid]
            s.name = r.get('name') or ''
            s.pt = int(r.get('pt', 0))
            s.rank = int(r.get('rank', 0))
            s.signature = r.get('signature') or ''
            s.updated_at = r.get('updated_at', s.updated_at)
        else:
            db.session.add(Score(
                event_id=event_id,
                uid=uid,
                name=r.get('name') or '',
                pt=int(r.get('pt', 0)),
                rank=int(r.get('rank', 0)),
                signature=r.get('signature') or '',
                updated_at=r.get('updated_at', now_ms())
            ))
    db.session.commit()


def chunked(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def append_chart_points_if_missing(event_id, points, chunk_size=400):
    event_id = str(event_id)
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


def append_player_score_history_if_missing(event_id, rows, batch_size=2000, chunk_size=400):
    if not rows:
        return 0

    event_id = str(event_id)
    tuples = [(str(row['uid']), row['timestamp']) for row in rows]
    existing_points = []
    for chunk in chunked(tuples, chunk_size):
        existing_points.extend(PlayerScoreHistory.query.filter(
            PlayerScoreHistory.event_id == event_id,
            db.tuple_(PlayerScoreHistory.uid, PlayerScoreHistory.timestamp).in_(chunk)
        ).all())
    existing = {(point.uid, point.timestamp): point for point in existing_points}

    changed = 0
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
        if len(batch) >= batch_size:
            db.session.bulk_save_objects(batch)
            changed += len(batch)
            batch = []

    if batch:
        db.session.bulk_save_objects(batch)
        changed += len(batch)
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
