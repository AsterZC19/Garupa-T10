import requests
import time
import json
import os
import sqlite3

# Path for the new player database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_DB_PATH = os.path.join(BASE_DIR, 'players.db')

# Caches for metadata
card_cache = {}
character_cache = None
area_item_cache = None

def get_card_data(card_id):
    if card_id in card_cache:
        return card_cache[card_id]
    try:
        r = requests.get(f"https://bestdori.com/api/cards/{card_id}.json", timeout=10)
        if r.status_code == 200:
            data = r.json()
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
        r = requests.get("https://bestdori.com/api/characters/all.2.json", timeout=10)
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
        r = requests.get("https://bestdori.com/api/areaitems/all.5.json", timeout=10)
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
    
    total_stats = {'performance': 0, 'technique': 0, 'visual': 0}
    enriched_cards = []
    
    characters = get_characters()
    area_items_meta = get_area_items()
    enabled_area_items = profile.get('enabledUserAreaItems', {}).get('entries', [])
    
    # Store card base + fixed stats for area item calculation
    card_base_stats = []
    
    for entry in main_deck:
        card_id = entry['situationId']
        level = entry['level']
        card_data = get_card_data(card_id)
        if not card_data:
            enriched_cards.append({"situationId": card_id})
            continue
            
        char_id = str(card_data.get('characterId'))
        band_id = characters.get(char_id, {}).get('bandId')
        rarity = card_data.get('rarity', 0)
        
        # 1. Base stats at level
        base_stats_map = card_data.get('stat', {}).get(str(level), {})
        perf = base_stats_map.get('performance', 0)
        tech = base_stats_map.get('technique', 0)
        vis = base_stats_map.get('visual', 0)
        
        # 2. Add fixed bonuses (Training, Episodes, Potential, Character Bonus)
        # In Bestdori mode=2, 'performance' in userAppendParameter usually includes Training + Episode bonuses.
        append = entry.get('userAppendParameter', {})
        perf += append.get('performance', 0) + append.get('characterPotentialPerformance', 0) + append.get('characterBonusPerformance', 0)
        tech += append.get('technique', 0) + append.get('characterPotentialTechnique', 0) + append.get('characterBonusTechnique', 0)
        vis += append.get('visual', 0) + append.get('characterPotentialVisual', 0) + append.get('characterBonusVisual', 0)
        
        # 3. Limit Break (Master Rank) Bonus
        lb_rank = entry.get('limitBreakRank', 0)
        if lb_rank > 0:
            lb_bonus = lb_rank * rarity * 50
            perf += lb_bonus
            tech += lb_bonus
            vis += lb_bonus
            
        card_base_stats.append({
            'perf': perf,
            'tech': tech,
            'vis': vis,
            'band_id': band_id,
            'attribute': card_data.get('attribute')
        })
        
        # Calculate rip_id for thumb URL
        rip_id = str(card_id // 50).zfill(3)
        
        enriched_cards.append({
            "situationId": card_id,
            "rarity": rarity,
            "attribute": card_data.get('attribute'),
            "bandId": band_id,
            "trainingStatus": entry.get('trainingStatus') == 'done',
            "resourceSetName": card_data.get('resourceSetName'),
            "rip_id": rip_id,
            "skillLevel": entry.get('skillLevel', 1),
            "limitBreakRank": lb_rank
        })

    # 4. Calculate Area Item Bonuses (Infrastructure)
    total_perf, total_tech, total_vis = 0, 0, 0
    
    for card in card_base_stats:
        bonus_perf, bonus_tech, bonus_vis = 0, 0, 0
        
        for item_entry in enabled_area_items:
            item_id = str(item_entry['areaItemId'])
            item_lv = item_entry['level']
            item_meta = area_items_meta.get(item_id)
            if not item_meta: continue
            
            target_attrs = item_meta.get('targetAttributes', [])
            target_bands = item_meta.get('targetBandIds', [])
            
            # Match logic: if list is empty, it applies to all.
            match_attr = not target_attrs or card['attribute'] in target_attrs
            match_band = not target_bands or card['band_id'] in target_bands
            
            if match_attr and match_band:
                # percentages are stored in maps keyed by level, JP server is index 0
                p_perc = item_meta.get('performance', {}).get(str(item_lv), [0])[0]
                t_perc = item_meta.get('technique', {}).get(str(item_lv), [0])[0]
                v_perc = item_meta.get('visual', {}).get(str(item_lv), [0])[0]
                
                bonus_perf += (p_perc * card['perf'] / 100)
                bonus_tech += (t_perc * card['tech'] / 100)
                bonus_vis += (v_perc * card['vis'] / 100)
        
        total_perf += card['perf'] + bonus_perf
        total_tech += card['tech'] + bonus_tech
        total_vis += card['vis'] + bonus_vis

    # Floor each category at the end as per game standard
    total_stats = {
        'performance': int(total_perf),
        'technique': int(total_tech),
        'visual': int(total_vis)
    }
    total_stats['total'] = total_stats['performance'] + total_stats['technique'] + total_stats['visual']
    
    return total_stats, enriched_cards

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

def get_player(uid):
    """
    Gets player data directly from the Bestdori API.
    """
    try:
        # Fetch main profile data using the comprehensive endpoint
        profile_url = f"https://bestdori.com/api/player/jp/{uid}?mode=2"
        response = requests.get(profile_url, timeout=15)
        if response.status_code != 200:
            return None # Player not found or API error
        
        api_data = response.json().get('data', {})
        if not api_data or not api_data.get('profile'):
            return None

        player_name = api_data.get('profile', {}).get('user', {}).get('name')

        # Fetch event data
        cheer_url = f"https://bestdori.com/api/player/jp/{uid}/cheer"
        cheer_response = requests.get(cheer_url, timeout=15)
        t10_events = []
        if cheer_response.status_code == 200:
            cheer_data = cheer_response.json().get('data', [])
            for event in cheer_data:
                if event.get('ranking') <= 10:
                    t10_events.append({
                        "event_id": event.get('eventId'),
                        "rank": event.get('ranking')
                    })
        
        # Sort events by ID descending to show newest first
        t10_events.sort(key=lambda x: x['event_id'], reverse=True)

        profile = api_data.get('profile', {})
        bp_data, enriched_cards = calculate_bp(profile)

        player_data = {
            "uid": uid,
            "name": player_name,
            "last_updated": int(time.time()),
            "t10_events": t10_events,
            "profile": profile, # Embed the full profile
            "bp": bp_data,
            "enriched_cards": enriched_cards
        }
        
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