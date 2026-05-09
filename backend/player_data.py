import requests
import time
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

# Path for the new player database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_DB_PATH = os.path.join(BASE_DIR, 'players.db')

BESTDORI_API_URL = "https://bestdori.com/api"
PLAYER_CACHE_TTL = 60

session = requests.Session()

# Caches for metadata
card_cache = {}
character_cache = None
area_item_cache = None
player_cache = {}

def fetch_json(path, timeout=10):
    r = session.get(f"{BESTDORI_API_URL}{path}", timeout=timeout)
    if r.status_code != 200:
        return None
    return r.json()


def get_card_data(card_id):
    if card_id in card_cache:
        return card_cache[card_id]
    try:
        data = fetch_json(f"/cards/{card_id}.json", timeout=10)
        if data:
            card_cache[card_id] = data
            return data
    except Exception as e:
        print(f"Error fetching card {card_id}: {e}")
    return None

def get_characters():
    global character_cache
    if character_cache:
        return character_cache
    try:
        r = session.get(f"{BESTDORI_API_URL}/characters/all.2.json", timeout=10)
        if r.status_code == 200:
            character_cache = r.json()
            return character_cache
    except Exception as e:
        print(f"Error fetching characters: {e}")
    return {}

def get_area_items():
    global area_item_cache
    if area_item_cache:
        return area_item_cache
    try:
        r = session.get(f"{BESTDORI_API_URL}/areaItems/main.5.json", timeout=10)
        if r.status_code == 200:
            area_item_cache = r.json()
            return area_item_cache
    except Exception as e:
        print(f"Error fetching area items: {e}")
    return {}

def calculate_bp(profile):
    main_deck = profile.get('mainDeckUserSituations', {}).get('entries', [])
    if not main_deck:
        return None

    characters = get_characters()
    area_items_meta = get_area_items()
    enabled_area_items = profile.get('enabledUserAreaItems', {}).get('entries', [])

    total_perf, total_tech, total_vis = 0, 0, 0
    enriched_cards = []
    card_list = []
    card_ids = [entry['situationId'] for entry in main_deck]
    with ThreadPoolExecutor(max_workers=min(5, len(card_ids))) as executor:
        card_data_map = dict(zip(card_ids, executor.map(get_card_data, card_ids)))

    for entry in main_deck:
        card_id = entry['situationId']
        card_data = card_data_map.get(card_id)
        if not card_data:
            enriched_cards.append({"situationId": card_id})
            continue

        char_id = str(card_data.get('characterId'))
        band_id = int(characters.get(char_id, {}).get('bandId', 0))
        attr = card_data.get('attribute')

        base_stats_map = card_data.get('stat', {}).get(str(entry['level']), {})
        p = base_stats_map.get('performance', 0)
        t = base_stats_map.get('technique', 0)
        v = base_stats_map.get('visual', 0)

        append = entry.get('userAppendParameter', {})
        p += append.get('performance', 0) + append.get('characterPotentialPerformance', 0) + append.get('characterBonusPerformance', 0)
        t += append.get('technique', 0) + append.get('characterPotentialTechnique', 0) + append.get('characterBonusTechnique', 0)
        v += append.get('visual', 0) + append.get('characterPotentialVisual', 0) + append.get('characterBonusVisual', 0)

        card_list.append({
            'p': p, 't': t, 'v': v,
            'attr': attr, 'band_id': band_id,
            'data': card_data, 'entry': entry
        })

    for card in card_list:
        card_p, card_t, card_v = card['p'], card['t'], card['v']
        bonus_p, bonus_t, bonus_v = 0, 0, 0

        for item in enabled_area_items:
            item_id = str(item.get('areaItemCategory'))
            item_lv = item.get('level')
            meta = area_items_meta.get(item_id)
            if not meta:
                continue

            target_attrs = meta.get('targetAttributes', [])
            target_bands = [int(b) for b in meta.get('targetBandIds', [])]
            if card['attr'] not in target_attrs or card['band_id'] not in target_bands:
                continue

            p_rate = meta.get('performance', {}).get(str(item_lv), [0])[0]
            t_rate = meta.get('technique', {}).get(str(item_lv), [0])[0]
            v_rate = meta.get('visual', {}).get(str(item_lv), [0])[0]

            bonus_p += card_p * p_rate / 100
            bonus_t += card_t * t_rate / 100
            bonus_v += card_v * v_rate / 100

        total_perf += card_p + bonus_p
        total_tech += card_t + bonus_t
        total_vis += card_v + bonus_v

        enriched_cards.append({
            "situationId": card['entry']['situationId'],
            "rarity": card['data'].get('rarity'),
            "attribute": card['attr'],
            "bandId": card['band_id'],
            "trainingStatus": card['entry'].get('trainingStatus') == 'done',
            "resourceSetName": card['data'].get('resourceSetName'),
            "rip_id": str(card['entry']['situationId'] // 50).zfill(3),
            "skillLevel": card['entry'].get('skillLevel', 1),
            "limitBreakRank": card['entry'].get('limitBreakRank', 0)
        })

    return {
        'performance': int(total_perf),
        'technique': int(total_tech),
        'visual': int(total_vis),
        'total': int(total_perf + total_tech + total_vis)
    }, enriched_cards

def init_player_db():
    """Initializes the player database and creates the table if it doesn't exist."""
    # This function is kept in case other parts of the app use it,
    # but it's no longer used for the primary player search.
    with sqlite3.connect(PLAYER_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                uid INTEGER PRIMARY KEY,
                name TEXT,
                last_updated INTEGER,
                t10_events TEXT
            )
        ''')
        conn.commit()

def get_player_profile(uid):
    return fetch_json(f"/player/jp/{uid}?mode=2", timeout=15)


def get_player_cheer(uid):
    return fetch_json(f"/player/jp/{uid}/cheer", timeout=15)


def get_player(uid):
    """
    Gets player data directly from the Bestdori API.
    """
    now = time.time()
    cached = player_cache.get(uid)
    if cached and now - cached['time'] < PLAYER_CACHE_TTL:
        return cached['data']

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            profile_future = executor.submit(get_player_profile, uid)
            cheer_future = executor.submit(get_player_cheer, uid)
            profile_response = profile_future.result()
            cheer_response = cheer_future.result()

        api_data = (profile_response or {}).get('data', {})
        if not api_data or not api_data.get('profile'):
            return None

        profile = api_data.get('profile', {})
        player_name = profile.get('user', {}).get('name') or profile.get('userName')

        t10_events = []
        cheer_data = (cheer_response or {}).get('data', [])
        for event in cheer_data:
            if event.get('ranking') <= 10:
                t10_events.append({
                    "event_id": event.get('eventId'),
                    "rank": event.get('ranking')
                })

        t10_events.sort(key=lambda x: x['event_id'], reverse=True)
        bp_data, enriched_cards = calculate_bp(profile)

        player_data = {
            "uid": uid,
            "name": player_name,
            "last_updated": int(now),
            "t10_events": t10_events,
            "profile": profile,
            "bp": bp_data,
            "enriched_cards": enriched_cards
        }
        player_cache[uid] = {'time': now, 'data': player_data}
        return player_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching player data for UID {uid}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_player for UID {uid}: {e}")
        return None

# To be safe, let's ensure the old DB functions don't interfere
# but we can't remove init_player_db as it's called on startup.
# We will just not call it from this file anymore.
# init_player_db()