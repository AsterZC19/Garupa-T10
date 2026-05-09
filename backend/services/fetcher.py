# Compatibility wrapper for older imports.
from services.bestdori_client import BESTDORI, client


def fetch_event_meta(event_id):
    return client.get_event_meta(event_id)


def fetch_top_data(event_id, server='jp'):
    return client.get_event_top_data(event_id, server=server, interval=900000)


def upsert_event_from_meta(event_id, meta):
    from services.event_ingestion import upsert_event_from_meta as _upsert_event_from_meta
    return _upsert_event_from_meta(event_id, meta)


def compute_speeds_and_store(event_id, top_json):
    from services.event_ingestion import compute_speeds_and_store as _compute_speeds_and_store
    return _compute_speeds_and_store(event_id, top_json)


def parse_and_store_event_data(event_id, server='jp'):
    from services.event_ingestion import parse_and_store_event_data as _parse_and_store_event_data
    return _parse_and_store_event_data(event_id, server=server)
