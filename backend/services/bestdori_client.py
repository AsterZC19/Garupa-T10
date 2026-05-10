import requests


BESTDORI = "https://bestdori.com"
BESTDORI_API_URL = f"{BESTDORI}/api"


class BestdoriClient:
    def __init__(self):
        self.session = requests.Session()

    def get_json(self, path, timeout=10):
        try:
            response = self.session.get(f"{BESTDORI_API_URL}{path}", timeout=timeout)
            if response.status_code != 200:
                return None
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Bestdori request failed: {path}: {e}")
            return None

    def asset_exists(self, url, timeout=5):
        try:
            response = self.session.head(url, timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def get_all_events(self):
        return self.get_json("/events/all.5.json", timeout=15)

    def get_event_meta(self, event_id):
        return self.get_json(f"/events/{event_id}.json", timeout=10)

    def get_event_top_data(self, event_id, server='jp', interval=60000):
        return self.get_json(f"/eventtop/data?server={server}&event={event_id}&mid=0&interval={interval}", timeout=60 if interval == 60000 else 15)

    def get_player_profile(self, uid, server='jp'):
        return self.get_json(f"/player/{server}/{uid}?mode=2", timeout=15)

    def get_player_cheer(self, uid, server='jp'):
        return self.get_json(f"/player/{server}/{uid}/cheer", timeout=15)

    def get_card(self, card_id):
        return self.get_json(f"/cards/{card_id}.json", timeout=10)

    def get_characters(self):
        return self.get_json("/characters/all.2.json", timeout=10)

    def get_area_items(self):
        return self.get_json("/areaItems/main.5.json", timeout=10)

    def get_degrees(self):
        return self.get_json("/degrees/all.3.json", timeout=10)


client = BestdoriClient()
