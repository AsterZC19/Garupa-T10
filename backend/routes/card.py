from flask import Blueprint, jsonify
import requests

card_bp = Blueprint('card', __name__)

BESTDORI_API_URL = 'https://bestdori.com/api'

@card_bp.route('/<int:card_id>')
def get_card_details(card_id):
    try:
        # Using a session object is better practice for connection pooling
        with requests.Session() as session:
            response = session.get(f'{BESTDORI_API_URL}/cards/{card_id}.json')
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            return jsonify(response.json())
    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors (e.g., card not found) gracefully
        return jsonify({"error": f"Failed to fetch card data: {e.response.status_code}"}), e.response.status_code
    except requests.exceptions.RequestException as e:
        # Handle other network-related errors
        return jsonify({"error": str(e)}), 500
