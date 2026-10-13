"""Separate current ranking membership from historical points and user metadata."""


def latest_snapshot_by_uid(points):
    """Return only players present at the newest snapshot timestamp.

    Both eventtop and monthlyRanking/top retain points and user profiles for
    former ranking members. Their last known scores are not current scores.
    Compare raw timestamps before any minute bucketing.
    """
    latest_ts = None
    snapshot = {}
    for point in points:
        timestamp = int(point.get('time') or point.get('timestamp') or 0)
        if latest_ts is None or timestamp > latest_ts:
            latest_ts = timestamp
            snapshot = {}
        if timestamp == latest_ts:
            uid = str(point['uid'])
            snapshot[uid] = {
                'uid': uid,
                'timestamp': timestamp,
                'pt': int(point.get('value') or 0),
            }
    return snapshot
