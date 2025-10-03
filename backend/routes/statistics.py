# backend/routes/statistics.py
from flask import Blueprint, jsonify
from services.statistics import calculate_hourly_stats

statistics_bp = Blueprint('statistics_bp', __name__)

@statistics_bp.route('/<event_id>/hourly_stats', methods=['GET'])
def get_hourly_stats(event_id):
    """
    Returns hourly statistics for an event, including score change counts
    and average PT per change.
    """
    stats = calculate_hourly_stats(event_id)
    return jsonify(stats)
