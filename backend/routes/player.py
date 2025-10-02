from flask import Blueprint, jsonify
from player_data import get_player

player_bp = Blueprint('player_bp', __name__)

@player_bp.route('/<int:uid>')
def get_player_route(uid):
    player_data = get_player(uid)
    if player_data:
        return jsonify(player_data)
    return jsonify({"error": "Player not found"}), 404
