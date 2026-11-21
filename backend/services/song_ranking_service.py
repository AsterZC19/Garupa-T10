"""Song Ranking (歌榜) T10 service.

Minimal-storage design:
- Active events: proxy upstream (EVENT_TOP_API_URL with allow_redirects=False,
  falling back to Bestdori) through a 5-minute in-memory TTLCache. Zero DB writes.
- Ended events: read single final snapshot per (event_id, music_id) from SQLite
  (`event_song_rankings`). If missing, lazy-backfill from Bestdori once and persist.
"""
import json
import logging
import threading
import time

import requests
from sqlalchemy import Integer, cast, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from models import Event, EventSongRanking, PlayerSongDegree, db
from services.bestdori_client import client as bestdori_client
from services.data_source_config import EVENT_TOP_API_URL
from services.ranking_snapshot import latest_snapshot_by_uid
from services.timeutil import now_ms
from services.ttl_cache import TTLCache

SONG_RANKING_EVENT_TYPES = frozenset({'challenge', 'versus', 'medley'})
BESTDORI_EVENT_TOP_URL = 'https://bestdori.com/api/eventtop/data'
BESTDORI_SONGS_URL = 'https://bestdori.com/api/songs/all.5.json'
SONG_RANKING_INTERVAL_MS = 3600000
ENDED_GRACE_PERIOD_MS = 30 * 60 * 1000  # Wait 30 min after end_at before permanently archiving
ACTIVE_CACHE_MAXSIZE = 64

_active_cache = TTLCache(300, maxsize=ACTIVE_CACHE_MAXSIZE)
_event_musics_cache = TTLCache(3600, maxsize=512)
_event_rewards_cache = TTLCache(3600, maxsize=512)
_songs_title_cache = TTLCache(21600, maxsize=4)
_persist_lock = threading.RLock()


def event_has_song_ranking(event_type):
    """Return True if the given eventType supports Song Ranking (歌榜)."""
    return (event_type or '').strip().lower() in SONG_RANKING_EVENT_TYPES


def _pick_title(titles):
    if isinstance(titles, list):
        if titles and titles[0]:
            return str(titles[0])
        for t in titles:
            if t:
                return str(t)
        return None
    return str(titles) if titles else None


def get_song_titles_map():
    """Fetch and cache {music_id: title} from Bestdori songs/all.5.json."""
    cached = _songs_title_cache.get('all')
    if cached is not None:
        return cached
    try:
        resp = bestdori_client.session.get(BESTDORI_SONGS_URL, timeout=15)
        if resp.status_code != 200:
            return {}
        raw = resp.json()
        if not isinstance(raw, dict):
            return {}
        title_map = {}
        for mid_str, info in raw.items():
            if not isinstance(info, dict):
                continue
            title = _pick_title(info.get('musicTitle'))
            if title and str(mid_str).lstrip('-').isdigit():
                title_map[int(mid_str)] = title
        return _songs_title_cache.set('all', title_map)
    except Exception as e:
        logging.warning(f"Failed to fetch Bestdori song titles: {e}")
        return {}


def _load_event_musics_meta(event_id):
    """Fetch and cache musics[0] ids and musicRankingRewards for an event."""
    eid_str = str(event_id)
    cached_ids = _event_musics_cache.get(eid_str)
    cached_rewards = _event_rewards_cache.get(eid_str)
    if cached_ids is not None and cached_rewards is not None:
        return cached_ids, cached_rewards

    meta = bestdori_client.get_event_meta(eid_str)
    if not isinstance(meta, dict):
        return [], {}
    musics = meta.get('musics')
    if not isinstance(musics, list) or not musics or not isinstance(musics[0], list):
        return [], {}

    music_ids = []
    rewards_by_mid = {}
    for entry in musics[0]:
        if not isinstance(entry, dict) or entry.get('musicId') is None:
            continue
        mid = int(entry['musicId'])
        if mid not in music_ids:
            music_ids.append(mid)
        rewards = entry.get('musicRankingRewards')
        if isinstance(rewards, list):
            rewards_by_mid[mid] = rewards
            if '_first' not in rewards_by_mid:
                rewards_by_mid['_first'] = rewards

    _event_musics_cache.set(eid_str, music_ids)
    _event_rewards_cache.set(eid_str, rewards_by_mid)
    return music_ids, rewards_by_mid


def get_event_music_ids(event_id, event_type):
    """Return list of music_ids for an event's song ranking ([-1] for medley)."""
    etype = (event_type or '').strip().lower()
    if etype not in SONG_RANKING_EVENT_TYPES:
        return []
    if etype == 'medley':
        return [-1]
    music_ids, _ = _load_event_musics_meta(event_id)
    return music_ids


def resolve_song_degree_id(event_id, music_id, rank):
    """Resolve Bestdori degree resourceId for (event_id, music_id, rank)."""
    if not rank or int(rank) <= 0:
        return None
    rank_int = int(rank)
    mid_int = int(music_id)
    _, rewards_by_mid = _load_event_musics_meta(event_id)
    if not rewards_by_mid:
        return None

    rewards = rewards_by_mid.get('_first') if mid_int == -1 else rewards_by_mid.get(mid_int)
    if not rewards:
        return None

    for item in rewards:
        if not isinstance(item, dict):
            continue
        if item.get('resourceType') != 'degree':
            continue
        from_rank = int(item.get('fromRank') or 0)
        to_rank = int(item.get('toRank') or 0)
        if from_rank <= rank_int <= to_rank and item.get('resourceId') is not None:
            return int(item['resourceId'])
    return None


def _fetch_eventtop_song(event_id, music_id, is_active, interval=SONG_RANKING_INTERVAL_MS):
    """Fetch raw eventtop payload for a song ranking.

    For active events, tries EVENT_TOP_API_URL with allow_redirects=False first
    (avoiding 302 HTML redirects on untracked events) and falls back to Bestdori.
    """
    params = {
        'server': 'jp',
        'event': int(event_id),
        'mid': int(music_id),
        'interval': interval,
    }

    if is_active and EVENT_TOP_API_URL != BESTDORI_EVENT_TOP_URL:
        try:
            resp = bestdori_client.session.get(
                EVENT_TOP_API_URL,
                params=params,
                timeout=15,
                allow_redirects=False,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and isinstance(data.get('points'), list) and len(data['points']) > 0:
                    return data
        except (requests.exceptions.RequestException, ValueError) as e:
            logging.debug(f"Primary song ranking fetch failed for {event_id}/{music_id}: {e}")

    try:
        resp = bestdori_client.session.get(
            BESTDORI_EVENT_TOP_URL,
            params=params,
            timeout=25 if interval == 60000 else 15,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
    except (requests.exceptions.RequestException, ValueError) as e:
        logging.warning(f"Bestdori song ranking fetch failed for {event_id}/{music_id}: {e}")
    return None


def extract_song_t10(top_json):
    """Extract sorted top-10 entries and latest snapshot timestamp from eventtop JSON."""
    if not isinstance(top_json, dict):
        return [], None
    points = top_json.get('points') or []
    if not points:
        return [], None

    current = latest_snapshot_by_uid(points)
    if not current:
        return [], None

    users = top_json.get('users') or []
    user_map = {str(u.get('uid')): u for u in users if isinstance(u, dict)}

    ranked = sorted(current.values(), key=lambda item: item['pt'], reverse=True)[:10]
    entries = []
    prev_score = None
    for idx, item in enumerate(ranked, start=1):
        uid_str = item['uid']
        user = user_map.get(uid_str, {})
        score = int(item['pt'])
        gap = 0 if idx == 1 else (prev_score - score)
        prev_score = score
        entries.append({
            'rank': idx,
            'uid': int(uid_str) if uid_str.isdigit() else uid_str,
            'name': user.get('name') or uid_str,
            'score': score,
            'gap': gap,
            'introduction': user.get('introduction') or '',
        })

    updated_at = max((item['timestamp'] for item in current.values()), default=None)
    return entries, updated_at


def _format_song_item(music_id, music_title, entries, updated_at):
    return {
        'music_id': int(music_id),
        'music_title': music_title,
        'is_medley_aggregate': int(music_id) == -1,
        'updated_at': updated_at,
        'entries': entries,
    }


def _fetch_songs_for_event(event_id, event_type, is_active):
    music_ids = get_event_music_ids(event_id, event_type)
    if not music_ids:
        return []

    titles_map = get_song_titles_map() if any(mid != -1 for mid in music_ids) else {}
    songs = []
    for mid in music_ids:
        payload = _fetch_eventtop_song(event_id, mid, is_active=is_active)
        if is_active and (payload is None or not (payload.get('points') or [])):
            # If larger interval returned None or no points yet, try 1-min interval once
            fallback = _fetch_eventtop_song(event_id, mid, is_active=is_active, interval=60000)
            if fallback is not None:
                payload = fallback
        entries, updated_at = extract_song_t10(payload)
        for entry in entries:
            entry['degree_id'] = resolve_song_degree_id(event_id, mid, entry['rank'])
        title = None if mid == -1 else titles_map.get(mid)
        songs.append(_format_song_item(mid, title, entries, updated_at))
    return songs


def _read_db_songs(event_id):
    rows = EventSongRanking.query.filter_by(event_id=int(event_id)).order_by(EventSongRanking.music_id.asc()).all()
    if not rows:
        return []
    songs = []
    for row in rows:
        try:
            entries = json.loads(row.entries_json) if row.entries_json else []
        except ValueError:
            entries = []
        songs.append(_format_song_item(row.music_id, row.music_title, entries, row.updated_at))
    return songs


def persist_ended_event_song_ranking(event):
    """Fetch final song ranking from Bestdori and persist 1 row per (event_id, music_id).

    Only persists songs with non-empty entries so transient upstream failures
    never poison SQLite or wipe existing archived snapshots.
    """
    eid = int(event.event_id)
    songs = _fetch_songs_for_event(eid, event.event_type, is_active=False)
    valid_songs = [song for song in songs if song.get('entries')]
    if not valid_songs:
        return []

    with _persist_lock:
        for song in valid_songs:
            mid = int(song['music_id'])
            serialized = json.dumps(song['entries'], ensure_ascii=False, separators=(',', ':'))
            stmt = sqlite_insert(EventSongRanking).values(
                event_id=eid,
                music_id=mid,
                music_title=song['music_title'],
                entries_json=serialized,
                updated_at=song['updated_at'],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['event_id', 'music_id'],
                set_={
                    'music_title': func.coalesce(stmt.excluded.music_title, EventSongRanking.music_title),
                    'entries_json': stmt.excluded.entries_json,
                    'updated_at': stmt.excluded.updated_at,
                },
            )
            db.session.execute(stmt)
        db.session.commit()
        sync_player_song_degrees_for_event(eid, valid_songs)

    try:
        from services.player_career_service import clear_career_cache
        clear_career_cache()
    except Exception:
        pass
    return valid_songs


def sync_player_song_degrees_for_event(event_id, songs):
    """Upsert/replace PlayerSongDegree rows in degrees.db for an event's non-empty songs."""
    eid = int(event_id)
    synced = 0
    with _persist_lock:
        for song in songs:
            entries = song.get('entries') or []
            if not entries:
                continue
            mid = int(song['music_id'])
            seen_uids = []
            seen_set = set()
            for entry in entries:
                uid_str = str(entry.get('uid') or '').strip()
                if not uid_str or uid_str in seen_set:
                    continue
                seen_set.add(uid_str)
                seen_uids.append(uid_str)
                stmt = sqlite_insert(PlayerSongDegree).values(
                    event_id=eid,
                    music_id=mid,
                    uid=uid_str,
                    music_title=song.get('music_title'),
                    name=entry.get('name') or uid_str,
                    rank=int(entry.get('rank') or 0),
                    score=int(entry.get('score') or 0),
                    degree_id=int(entry['degree_id']) if entry.get('degree_id') is not None else None,
                    updated_at=song.get('updated_at'),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['event_id', 'music_id', 'uid'],
                    set_={
                        'music_title': func.coalesce(stmt.excluded.music_title, PlayerSongDegree.music_title),
                        'name': stmt.excluded.name,
                        'rank': stmt.excluded.rank,
                        'score': stmt.excluded.score,
                        'degree_id': stmt.excluded.degree_id,
                        'updated_at': stmt.excluded.updated_at,
                    },
                )
                db.session.execute(stmt)
                synced += 1
            if seen_uids:
                PlayerSongDegree.query.filter(
                    PlayerSongDegree.event_id == eid,
                    PlayerSongDegree.music_id == mid,
                    PlayerSongDegree.uid.notin_(seen_uids),
                ).delete(synchronize_session=False)
        db.session.commit()
    return synced


def sync_all_player_song_degrees_from_rankings():
    """Backfill PlayerSongDegree in degrees.db from existing EventSongRanking rows."""
    existing_pairs = {
        (int(r[0]), int(r[1]))
        for r in db.session.query(PlayerSongDegree.event_id, PlayerSongDegree.music_id).distinct().all()
    }
    rows = EventSongRanking.query.order_by(EventSongRanking.event_id.desc(), EventSongRanking.music_id.asc()).all()
    synced_songs = 0
    for row in rows:
        key = (int(row.event_id), int(row.music_id))
        if key in existing_pairs:
            continue
        try:
            entries = json.loads(row.entries_json) if row.entries_json else []
        except ValueError:
            entries = []
        if not entries:
            continue
        sync_player_song_degrees_for_event(row.event_id, [{
            'music_id': row.music_id,
            'music_title': row.music_title,
            'updated_at': row.updated_at,
            'entries': entries,
        }])
        existing_pairs.add(key)
        synced_songs += 1
    return synced_songs


def get_event_song_ranking(event, force_refresh=False):
    """Return full API response dict for GET /api/events/<event_id>/song_ranking."""
    eid = int(event.event_id)
    etype = event.event_type or ''
    if not event_has_song_ranking(etype):
        return {
            'event_id': eid,
            'event_type': etype,
            'has_song_ranking': False,
            'is_active': False,
            'source': 'none',
            'songs': [],
        }

    now = now_ms()
    is_upcoming = bool(event.start_at and event.start_at > now)
    is_active = bool(event.start_at and event.start_at <= now and (not event.end_at or event.end_at >= now))
    in_grace_period = bool(event.end_at and event.end_at < now <= event.end_at + ENDED_GRACE_PERIOD_MS)

    if is_upcoming:
        return {
            'event_id': eid,
            'event_type': etype,
            'has_song_ranking': True,
            'is_active': False,
            'source': 'none',
            'songs': [],
        }

    if is_active or in_grace_period:
        cache_key = ('active', eid)
        if not force_refresh:
            cached = _active_cache.get(cache_key)
            if cached is not None:
                return cached
        songs = _fetch_songs_for_event(eid, etype, is_active=True)
        result = {
            'event_id': eid,
            'event_type': etype,
            'has_song_ranking': True,
            'is_active': is_active,
            'source': 'live',
            'songs': songs,
        }
        return _active_cache.set(cache_key, result)

    # Ended event (past grace period): read from SQLite first
    db_songs = _read_db_songs(eid)
    if db_songs and not force_refresh:
        return {
            'event_id': eid,
            'event_type': etype,
            'has_song_ranking': True,
            'is_active': False,
            'source': 'db',
            'songs': db_songs,
        }

    # Missing in DB (or forced refresh): lazy-backfill from Bestdori and persist
    songs = persist_ended_event_song_ranking(event)
    if not songs and db_songs:
        # Upstream failed during forced refresh — keep serving archived DB snapshot
        return {
            'event_id': eid,
            'event_type': etype,
            'has_song_ranking': True,
            'is_active': False,
            'source': 'db',
            'songs': db_songs,
        }
    return {
        'event_id': eid,
        'event_type': etype,
        'has_song_ranking': True,
        'is_active': False,
        'source': 'backfill' if songs else 'none',
        'songs': songs,
    }


def backfill_ended_song_rankings(limit=None, sleep_seconds=0.5):
    """Backfill final song rankings for ended events and sync player_song_degrees."""
    sync_all_player_song_degrees_from_rankings()
    now = now_ms()
    ended_cutoff = now - ENDED_GRACE_PERIOD_MS
    ended_events = Event.query.filter(
        Event.end_at > 0,
        Event.end_at < ended_cutoff,
        Event.event_type.in_(tuple(SONG_RANKING_EVENT_TYPES)),
    ).order_by(cast(Event.event_id, Integer).desc()).all()

    if not ended_events:
        return 0

    existing_eids = {
        int(row[0]) for row in db.session.query(EventSongRanking.event_id).distinct().all()
    }
    missing = [e for e in ended_events if str(e.event_id).isdigit() and int(e.event_id) not in existing_eids]
    if limit is not None:
        missing = missing[:limit]

    processed = 0
    for idx, event in enumerate(missing):
        try:
            songs = persist_ended_event_song_ranking(event)
            if songs:
                processed += 1
                logging.info(f"Song ranking backfill: stored {len(songs)} song(s) for event {event.event_id}.")
        except Exception as e:
            logging.error(f"Song ranking backfill failed for event {event.event_id}: {e}", exc_info=True)
            db.session.rollback()
        if sleep_seconds and idx < len(missing) - 1:
            time.sleep(sleep_seconds)
    return processed
