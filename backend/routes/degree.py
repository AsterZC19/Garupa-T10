from flask import Blueprint, jsonify
from models import PlayerDegree
from services.bestdori_client import client
from services.ttl_cache import TTLCache

degree_bp = Blueprint('degree_bp', __name__)

degrees_cache = TTLCache(24 * 3600)

@degree_bp.route('/all.3.json', methods=['GET'])
def get_all_degrees():
    cached = degrees_cache.get('degrees')
    if cached is not None:
        return jsonify(cached)
    data = client.get_degrees()
    if data is None:
        return jsonify({"error": "Failed to fetch degrees data"}), 500
    return jsonify(degrees_cache.set('degrees', data))

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
