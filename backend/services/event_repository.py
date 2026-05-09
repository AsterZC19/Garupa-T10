from datetime import datetime
from sqlalchemy import Integer, cast
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


def list_events():
    return Event.query.order_by(Event.start_at.desc()).all()


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
    Score.query.filter_by(event_id=str(event_id)).delete()
    if rows:
        db.session.bulk_insert_mappings(Score, rows)
    db.session.commit()


def append_chart_points_if_missing(event_id, points):
    existing = set()
    for item in ChartPoint.query.with_entities(ChartPoint.uid, ChartPoint.timestamp).filter_by(event_id=str(event_id)).all():
        existing.add((item.uid, item.timestamp))

    to_add = []
    for point in points:
        key = (str(point['uid']), point['timestamp'])
        if key not in existing:
            to_add.append(ChartPoint(
                event_id=str(event_id),
                uid=key[0],
                name=point.get('name', ''),
                timestamp=point['timestamp'],
                pt=point['pt']
            ))
    if to_add:
        db.session.bulk_save_objects(to_add)
        db.session.commit()
    return len(to_add)


def append_player_score_history_if_missing(event_id, rows):
    if not rows:
        return 0

    existing_points = PlayerScoreHistory.query.with_entities(
        PlayerScoreHistory.uid,
        PlayerScoreHistory.timestamp
    ).filter_by(event_id=str(event_id)).all()
    existing = set(existing_points)

    to_add = []
    for row in rows:
        key = (str(row['uid']), row['timestamp'])
        if key not in existing:
            to_add.append(PlayerScoreHistory(
                event_id=str(event_id),
                uid=key[0],
                name=row.get('name') or key[0],
                pt=row['pt'],
                timestamp=row['timestamp']
            ))
    if to_add:
        db.session.bulk_save_objects(to_add)
        db.session.commit()
    return len(to_add)


def get_scores(event_id, limit):
    return Score.query.filter_by(event_id=str(event_id)).order_by(Score.rank.asc()).limit(limit).all()


def get_chart_history(event_id):
    return PlayerScoreHistory.query.with_entities(
        PlayerScoreHistory.uid,
        PlayerScoreHistory.name,
        PlayerScoreHistory.timestamp,
        PlayerScoreHistory.pt
    ).filter_by(event_id=str(event_id)).order_by(PlayerScoreHistory.timestamp.asc()).all()


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
