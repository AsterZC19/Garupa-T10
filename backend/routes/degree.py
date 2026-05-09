from flask import Blueprint, jsonify
from models import db, PlayerDegree
import requests

degree_bp = Blueprint('degree_bp', __name__)

BESTDORI_API_URL = 'https://bestdori.com/api'
degrees_cache = None

@degree_bp.route('/all.3.json', methods=['GET'])
def get_all_degrees():
    global degrees_cache
    if degrees_cache is not None:
        return jsonify(degrees_cache)
    try:
        response = requests.get(f'{BESTDORI_API_URL}/degrees/all.3.json', timeout=10)
        response.raise_for_status()
        degrees_cache = response.json()
        return jsonify(degrees_cache)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@degree_bp.route('/player/<uid>/all_degrees')
def get_player_all_degrees(uid):
    """
    Get all T10 event achievements for a given player.
    Returns a simple list of event_id and rank.
    """
    try:
        achievements = PlayerDegree.query.filter_by(uid=uid).order_by(PlayerDegree.event_id.desc()).all()

        result = [
            {"event_id": ach.event_id, "rank": ach.rank}
            for ach in achievements
        ]

        return jsonify(result)

    except Exception as e:
        print(f"Error fetching degrees for UID {uid}: {e}")
        return jsonify({"error": "An error occurred while fetching degrees"}), 500
