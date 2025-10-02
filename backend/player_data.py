import requests
import time
import json
import os
import sqlite3

# Path for the new player database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_DB_PATH = os.path.join(BASE_DIR, 'players.db')

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

        player_data = {
            "uid": uid,
            "name": player_name,
            "last_updated": int(time.time()),
            "t10_events": t10_events,
            "profile": api_data.get('profile') # Embed the full profile
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