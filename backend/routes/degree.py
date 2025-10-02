from flask import Blueprint, jsonify
import requests

degree_bp = Blueprint('degree', __name__)

BESTDORI_API_URL = 'https://bestdori.com/api'

@degree_bp.route('/all.3.json', methods=['GET'])
def get_all_degrees():
    try:
        response = requests.get(f'{BESTDORI_API_URL}/degrees/all.3.json')
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
