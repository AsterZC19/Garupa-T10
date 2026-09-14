"""独立榜单接口配置；进程环境变量优先于 backend/.env。"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')


def env_url(name, default):
    return (os.environ.get(name, '').strip() or default).rstrip('/')


GARUPA_TRACKER_BASE = env_url('GARUPA_TRACKER_BASE', 'http://127.0.0.1:5519/api')


def endpoint(name, path, default):
    origin = env_url(name, '')
    return f'{origin}/api/{path}' if origin else default


EVENT_TOP_API_URL = endpoint('EVENT_TOP_BASE_URL', 'eventtop/data', 'https://bestdori.com/api/eventtop/data')
MONTHLY_INFO_API_URL = endpoint('MONTHLY_INFO_BASE_URL', 'monthlyRanking/info.json', f'{GARUPA_TRACKER_BASE}/monthlyRanking/info.json')
MONTHLY_TOP_API_URL = endpoint('MONTHLY_TOP_BASE_URL', 'monthlyRanking/top', f'{GARUPA_TRACKER_BASE}/monthlyRanking/top')
