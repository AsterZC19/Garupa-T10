"""Read-only career record aggregation across events, monthly, and song rankings."""
import json
from collections import defaultdict
from sqlalchemy import Integer, cast

from models import (
    ChartDataCache,
    ChartPoint,
    Event,
    MonthlyChartPoint,
    MonthlyRanking,
    MonthlyScore,
    PlayerDegree,
    PlayerScoreHistory,
    PlayerSongDegree,
    Score,
)
from services.timeutil import now_ms
from services.ttl_cache import TTLCache


career_cache = TTLCache(120, maxsize=512)


def clear_career_cache():
    career_cache.clear()


def _ref_uids_for_group(sorted_rows):
    """Return (top1_uid, top10_uid) from a rank-sorted score group."""
    if not sorted_rows:
        return None, None
    top1_uid = str(sorted_rows[0].uid)
    top10_row = next((r for r in sorted_rows if r.rank == 10), None)
    if top10_row is None and len(sorted_rows) >= 10:
        top10_row = sorted_rows[9]
    top10_uid = str(top10_row.uid) if top10_row is not None else None
    return top1_uid, top10_uid


def _compute_gaps_for_group(sorted_rows, target_uid):
    """Return (gap_to_first, gap_to_prev, lead_to_second) for target_uid in a ranked score list."""
    if not sorted_rows:
        return None, None, None

    top1_pt = int(sorted_rows[0].pt or 0)
    second_pt = int(sorted_rows[1].pt or 0) if len(sorted_rows) >= 2 else None

    for idx, row in enumerate(sorted_rows):
        if str(row.uid) != target_uid:
            continue
        pt = int(row.pt or 0)
        rank = int(row.rank) if getattr(row, 'rank', None) and row.rank > 0 else idx + 1
        gap_to_first = (top1_pt - pt) if rank > 1 else 0
        gap_to_prev = (int(sorted_rows[idx - 1].pt or 0) - pt) if idx > 0 else None
        lead_to_second = (pt - second_pt) if (rank == 1 and second_pt is not None) else None
        return gap_to_first, gap_to_prev, lead_to_second

    return None, None, None


def _build_event_records(uid):
    player_scores = (
        Score.query.filter(Score.uid == uid, Score.event_id != '5001')
        .order_by(cast(Score.event_id, Integer).desc())
        .all()
    )
    score_by_event = {str(s.event_id): s for s in player_scores if (s.rank or 0) <= 10}

    degree_rows = (
        PlayerDegree.query.filter(PlayerDegree.uid == uid, PlayerDegree.event_id != '5001')
        .order_by(cast(PlayerDegree.event_id, Integer).desc())
        .all()
    )
    degree_by_event = {str(d.event_id): d for d in degree_rows}

    all_event_ids = sorted(
        set(score_by_event.keys()) | set(degree_by_event.keys()),
        key=lambda eid: int(eid) if eid.isdigit() else 0,
        reverse=True,
    )
    if not all_event_ids:
        return []

    events_map = {
        str(ev.event_id): ev
        for ev in Event.query.filter(Event.event_id.in_(all_event_ids)).all()
    }

    local_event_ids = list(score_by_event.keys())
    scores_by_event = defaultdict(list)
    chart_event_ids = set()

    if local_event_ids:
        for row in Score.query.filter(Score.event_id.in_(local_event_ids)).all():
            scores_by_event[str(row.event_id)].append(row)
        for rows in scores_by_event.values():
            rows.sort(key=lambda r: (r.rank if r.rank and r.rank > 0 else 999, -(r.pt or 0)))

        chart_event_ids.update(
            str(r[0]) for r in ChartDataCache.query.with_entities(ChartDataCache.event_id)
            .filter(
                ChartDataCache.uid == uid,
                ChartDataCache.bucket_interval == '15m',
                ChartDataCache.event_id.in_(local_event_ids),
            )
            .distinct().all()
        )
        current_time_ms = now_ms()
        # Match event_query_service.get_chart_series: old pruned events (>24h after end)
        # return {} when 15m ChartDataCache is absent instead of falling back to raw history.
        live_fallback_ids = [
            eid for eid in local_event_ids
            if eid not in chart_event_ids
            and not (
                events_map.get(eid)
                and (events_map[eid].end_at or 0) > 0
                and current_time_ms > events_map[eid].end_at + 24 * 3600 * 1000
            )
        ]
        if live_fallback_ids:
            chart_event_ids.update(
                str(r[0]) for r in PlayerScoreHistory.query.with_entities(PlayerScoreHistory.event_id)
                .filter(PlayerScoreHistory.uid == uid, PlayerScoreHistory.event_id.in_(live_fallback_ids))
                .distinct().all()
            )
            still_missing_ids = [eid for eid in live_fallback_ids if eid not in chart_event_ids]
            if still_missing_ids:
                chart_event_ids.update(
                    str(r[0]) for r in ChartPoint.query.with_entities(ChartPoint.event_id)
                    .filter(ChartPoint.uid == uid, ChartPoint.event_id.in_(still_missing_ids))
                    .distinct().all()
                )

    records = []
    for eid in all_event_ids:
        s = score_by_event.get(eid)
        d = degree_by_event.get(eid)
        ev = events_map.get(eid)

        if s is not None:
            group = scores_by_event.get(eid, [])
            gap_to_first, gap_to_prev, lead_to_second = _compute_gaps_for_group(group, uid)
            top1_uid, top10_uid = _ref_uids_for_group(group)
            rank = int(s.rank) if s.rank and s.rank > 0 else (int(d.rank) if d else 0)
            records.append({
                'event_id': eid,
                'rank': rank,
                'pt': int(s.pt or 0),
                'name_used': s.name or '',
                'signature': s.signature or '',
                'event_name': ev.name if ev else None,
                'event_type': ev.event_type if ev else None,
                'start_at': ev.start_at if ev else None,
                'end_at': ev.end_at if ev else None,
                'banner_url': ev.banner_url if ev else None,
                'gap_to_first': gap_to_first,
                'gap_to_prev': gap_to_prev,
                'lead_to_second': lead_to_second,
                'top1_uid': top1_uid,
                'top10_uid': top10_uid,
                'has_local_detail': True,
                'has_chart': eid in chart_event_ids,
            })
        elif d is not None:
            records.append({
                'event_id': eid,
                'rank': int(d.rank or 0),
                'pt': None,
                'name_used': None,
                'signature': '',
                'event_name': ev.name if ev else None,
                'event_type': ev.event_type if ev else None,
                'start_at': ev.start_at if ev else None,
                'end_at': ev.end_at if ev else None,
                'banner_url': ev.banner_url if ev else None,
                'gap_to_first': None,
                'gap_to_prev': None,
                'lead_to_second': None,
                'has_local_detail': False,
                'has_chart': False,
            })

    return records


def _build_monthly_records(uid):
    player_monthly = (
        MonthlyScore.query.filter(MonthlyScore.uid == uid)
        .order_by(MonthlyScore.monthly_id.desc())
        .all()
    )
    if not player_monthly:
        return []

    monthly_ids = [int(m.monthly_id) for m in player_monthly]
    periods_map = {
        int(p.monthly_id): p
        for p in MonthlyRanking.query.filter(MonthlyRanking.monthly_id.in_(monthly_ids)).all()
    }

    scores_by_monthly = defaultdict(list)
    for row in MonthlyScore.query.filter(MonthlyScore.monthly_id.in_(monthly_ids)).all():
        scores_by_monthly[int(row.monthly_id)].append(row)
    for rows in scores_by_monthly.values():
        rows.sort(key=lambda r: (r.rank if r.rank and r.rank > 0 else 999, -(r.pt or 0)))

    chart_monthly_ids = {
        int(r[0]) for r in MonthlyChartPoint.query.with_entities(MonthlyChartPoint.monthly_id)
        .filter(MonthlyChartPoint.uid == uid, MonthlyChartPoint.monthly_id.in_(monthly_ids))
        .distinct().all()
    }

    records = []
    for m in player_monthly:
        mid = int(m.monthly_id)
        period = periods_map.get(mid)
        group = scores_by_monthly.get(mid, [])
        gap_to_first, gap_to_prev, lead_to_second = _compute_gaps_for_group(group, uid)
        top1_uid, top10_uid = _ref_uids_for_group(group)
        records.append({
            'monthly_id': mid,
            'name': period.name if period else None,
            'start_at': period.start_at if period else None,
            'end_at': period.end_at if period else None,
            'banner_url': period.banner_url if period else None,
            'rank': int(m.rank or 0),
            'pt': int(m.pt or 0),
            'name_used': m.name or '',
            'signature': m.signature or '',
            'degree_id': m.degree_id,
            'gap_to_first': gap_to_first,
            'gap_to_prev': gap_to_prev,
            'lead_to_second': lead_to_second,
            'top1_uid': top1_uid,
            'top10_uid': top10_uid,
            'has_chart': mid in chart_monthly_ids,
        })
    return records


def _build_song_ranking_records(uid):
    """Query indexed PlayerSongDegree in degrees.db (zero external HTTP calls)."""
    rows = (
        PlayerSongDegree.query
        .filter(PlayerSongDegree.uid == uid)
        .order_by(PlayerSongDegree.event_id.desc(), PlayerSongDegree.music_id.asc())
        .all()
    )
    if not rows:
        return []

    matched_eids = list({str(r.event_id) for r in rows})
    events_map = {
        str(ev.event_id): ev
        for ev in Event.query.filter(Event.event_id.in_(matched_eids)).all()
    }

    records = []
    for row in rows:
        ev = events_map.get(str(row.event_id))
        records.append({
            'event_id': int(row.event_id),
            'event_name': ev.name if ev else None,
            'event_type': ev.event_type if ev else None,
            'music_id': int(row.music_id),
            'music_title': row.music_title,
            'is_medley_aggregate': int(row.music_id) == -1,
            'rank': int(row.rank or 0),
            'score': int(row.score or 0),
            'degree_id': int(row.degree_id) if row.degree_id is not None else None,
            'name': row.name or uid,
            'updated_at': row.updated_at,
        })
    return records


def get_player_career(uid):
    """Return a player's locally archived event, monthly, and song T10 career records."""
    uid_str = str(uid).strip()
    if not uid_str:
        return {'uid': '', 'events': [], 'monthly': [], 'song_ranking_records': []}

    cached = career_cache.get(uid_str)
    if cached is not None:
        return cached

    payload = {
        'uid': uid_str,
        'events': _build_event_records(uid_str),
        'monthly': _build_monthly_records(uid_str),
        'song_ranking_records': _build_song_ranking_records(uid_str),
    }
    if payload['events'] or payload['monthly'] or payload['song_ranking_records']:
        return career_cache.set(uid_str, payload)
    return payload
