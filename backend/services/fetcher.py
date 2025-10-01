# backend/services/fetcher.py
import requests
import json
from datetime import datetime
from models import db
from models import Event, Score, ChartPoint
import time
import csv
import os

BESTDORI = "https://bestdori.com"

def now_ms():
    return int(datetime.utcnow().timestamp() * 1000)

def fetch_event_meta(event_id):
    try:
        url = f"{BESTDORI}/api/events/{event_id}.json"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        print("fetch_event_meta error", e)
        return None

def fetch_top_data(event_id, server='jp'):
    try:
        url = f"{BESTDORI}/api/eventtop/data?server={server}&event={event_id}&mid=0&interval=900000"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        print("fetch_top_data error", e)
        return None

def upsert_event_from_meta(event_id, meta):
    # meta may contain lists for names/start/end
    name = meta.get('eventName')
    if isinstance(name, list):
        name = name[0] if name else ''
    evtype = meta.get('eventType')
    start_at = None
    end_at = None
    if 'startAt' in meta:
        sa = meta['startAt']
        if isinstance(sa, list) and len(sa) > 0 and sa[0] is not None:
            start_at = int(sa[0])
        elif not isinstance(sa, list) and sa is not None:
            start_at = int(sa)
    if 'endAt' in meta:
        ea = meta['endAt']
        if isinstance(ea, list) and len(ea) > 0 and ea[0] is not None:
            end_at = int(ea[0])
        elif not isinstance(ea, list) and ea is not None:
            end_at = int(ea)

    banner_url = None
    asset_bundle_name = meta.get('assetBundleName')
    if asset_bundle_name:
        # 1. 拼接主要图片地址
        primary_url = f"{BESTDORI}/assets/jp/event/{asset_bundle_name}/images_rip/banner.png"
        try:
            # 使用 HEAD 请求检查图片是否存在，避免下载整个图片
            r = requests.head(primary_url, timeout=5)
            if r.status_code == 200:
                banner_url = primary_url
        except requests.exceptions.RequestException:
            pass  # 网络问题或超时，则继续尝试备用地址

    # 2. 如果主要地址无效，则尝试备用地址
    if not banner_url:
        banner_asset_bundle_name = meta.get('bannerAssetBundleName')
        if banner_asset_bundle_name:
            fallback_url = f"{BESTDORI}/assets/jp/homebanner_rip/{banner_asset_bundle_name}.png"
            try:
                r = requests.head(fallback_url, timeout=5)
                if r.status_code == 200:
                    banner_url = fallback_url
            except requests.exceptions.RequestException:
                pass # 如果都失败，banner_url 将为 None

    ev = Event.query.filter_by(event_id=str(event_id)).first()
    if not ev:
        ev = Event(event_id=str(event_id), name=name, event_type=evtype, start_at=start_at or 0, end_at=end_at or 0, banner_url=banner_url, updated_at=now_ms())
        db.session.add(ev)
    else:
        ev.name = name
        ev.event_type = evtype
        ev.start_at = start_at or ev.start_at
        ev.end_at = end_at or ev.end_at
        ev.banner_url = banner_url or ev.banner_url
        ev.updated_at = now_ms()
    db.session.commit()
    return ev

def compute_speeds_and_store(event_id, top_json):
    """
    top_json contains 'points' and 'users' similar to your data.py.
    We'll:
    - build latest points per uid
    - compare with prior chart points to compute speed (delta since last saved timestamp per uid)
    - store scores (one snapshot) and append chart points
    """
    if top_json is None:
        return
    points = top_json.get('points', [])  # list of dicts with uid, time, value
    users = top_json.get('users', [])    # list of dicts with uid, name, introduction, ranking (maybe)

    # Build latest pts by uid from 'points' (the last point per uid)
    latest_by_uid = {}
    for p in points:
        uid = str(p.get('uid'))
        t = int(p.get('time'))
        v = int(p.get('value', 0))
        # keep the last (largest time)
        if uid not in latest_by_uid or t > latest_by_uid[uid]['t']:
            latest_by_uid[uid] = {'t': t, 'v': v}

    # Save chart points: append every point entry (could be large; consider sampling)
    # We only append unique (uid,t) pairs to avoid duplicates
    existing = set()
    q = ChartPoint.query.filter_by(event_id=str(event_id)).all()
    for e in q:
        existing.add((e.uid, e.timestamp))
    to_add_chart = []
    for p in points:
        uid = str(p.get('uid'))
        t = int(p.get('time'))
        v = int(p.get('value', 0))
        if (uid, t) not in existing:
            cp = ChartPoint(event_id=str(event_id), uid=uid, name='', timestamp=t, pt=v)
            to_add_chart.append(cp)
    if to_add_chart:
        db.session.bulk_save_objects(to_add_chart)
        db.session.commit()

    # Compute per-uid speed by comparing with previous timestamp for that uid
    # We'll find the latest chart point before current time for uid and calculate delta/time
    # For simplicity (像你 data.py 的做法)，先 look for last chartpoint in DB (previous record).
    speeds = {}  # uid -> (delta_points, delta_hours)
    for uid, latest in latest_by_uid.items():
        # find previous chart point for uid (largest timestamp < latest.t)
        prev = ChartPoint.query.filter(ChartPoint.event_id==str(event_id), ChartPoint.uid==uid, ChartPoint.timestamp < latest['t']).order_by(ChartPoint.timestamp.desc()).first()
        if prev:
            delta_pts = latest['v'] - prev.pt
            delta_ms = latest['t'] - prev.timestamp
            # convert to per-hour
            delta_hours = delta_ms / (1000.0 * 3600.0)
            speed_per_hour = int(delta_pts / delta_hours) if delta_hours > 0 else 0
            speeds[uid] = {'delta': delta_pts, 'speed_h': speed_per_hour}
        else:
            # no previous: speed undefined — use delta value as raw / mark as -1
            speeds[uid] = {'delta': latest['v'], 'speed_h': -1}

    # Save snapshot scores (clear existing snapshot scores for that event then insert)
    # We decide latest snapshot is "users" list or ordering in latest_by_uid
    Score.query.filter_by(event_id=str(event_id)).delete()
    db.session.commit()

    # Determine the latest timestamp from the fetched data
    event = Event.query.filter_by(event_id=str(event_id)).first()
    if not event:
        print(f"[Error] compute_speeds_and_store: Event {event_id} not found in DB.")
        # Cannot proceed without event context for fallbacks
        return

    latest_data_timestamp = 0
    if points:
        latest_data_timestamp = max(p.get('time', 0) for p in points)

    # If no timestamp found in data, create a fallback
    if latest_data_timestamp == 0:
        now = now_ms()
        # For past events, use the event's end time as the timestamp
        if now > event.end_at and event.end_at > 0:
            latest_data_timestamp = event.end_at
        else: # For ongoing events, using current time is acceptable
            latest_data_timestamp = now

    # we prefer 'users' if present for name and ranking
    if users and len(users) > 0:
        # augment scores with speeds if available
        for u in users:
            uid = str(u.get('uid'))
            name = u.get('name') or ''
            rank = u.get('ranking') or None
            pt = int(u.get('current_pt') or (latest_by_uid.get(uid, {}).get('v', 0)))
            sig = u.get('introduction') or ''
            s = Score(event_id=str(event_id), uid=uid, name=name, pt=pt, rank=rank or 0, signature=sig, updated_at=latest_data_timestamp)
            db.session.add(s)
    else:
        # fallback: use latest_by_uid sorted by value
        arr = [(uid, info['v']) for uid, info in latest_by_uid.items()]
        arr.sort(key=lambda x: x[1], reverse=True)
        for idx, (uid, v) in enumerate(arr):
            s = Score(event_id=str(event_id), uid=uid, name=uid, pt=v, rank=idx+1, signature='', updated_at=latest_data_timestamp)
            db.session.add(s)
    db.session.commit()

    # Optional: update ChartPoint names from Score table for readability
    scores_now = Score.query.filter_by(event_id=str(event_id)).all()
    name_map = {s.uid: s.name for s in scores_now}
    ChartPoint.query.filter_by(event_id=str(event_id)).update({'name': ''})
    db.session.commit()
    # We won't mass update ChartPoint.name (could be heavy). On read we can merge names.

def parse_and_store_event_data(event_id, server='jp'):
    meta = fetch_event_meta(event_id)
    if not meta:
        print(f"event meta {event_id} not found")
        return False
    ev = upsert_event_from_meta(event_id, meta)

    top = fetch_top_data(event_id, server)
    if top is None:
        print("no top data")
        return True  # meta still updated

    compute_speeds_and_store(event_id, top)
    return True
