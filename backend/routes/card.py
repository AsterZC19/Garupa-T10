from flask import Blueprint, jsonify
from player_data import get_card_data

card_bp = Blueprint('card', __name__)

@card_bp.route('/<int:card_id>')
def get_card_details(card_id):
    card_data = get_card_data(card_id)
    if not card_data:
        return jsonify({"error": "Failed to fetch card data"}), 404
    return jsonify(card_data)
