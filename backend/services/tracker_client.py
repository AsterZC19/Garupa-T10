# backend/services/tracker_client.py
"""GarupaSpeedTracker 后端客户端（月榜数据源）。

复用 StarFreedomX/GarupaSpeedTracker 已部署的后端 API（该后端已持有官方 API
的设备签名，我们这边无需再连官方接口 / 配置签名）。地址通过环境变量
GARUPA_TRACKER_BASE 配置。

数据源接口：
- GET {base}/monthlyRanking/info.json          → 全部月榜期 {id: {name, assetBundleName, startAt[], endAt[]}}
- GET {base}/monthlyRanking/top?server=0&monthlyId=X → {points:[{time,uid,value}], users:[...]}
"""
import os
import requests

from services.ttl_cache import TTLCache

# 加载 backend/.env（若存在）中的 GARUPA_TRACKER_* 配置
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
except Exception:
    pass

GARUPA_TRACKER_BASE = os.environ.get('GARUPA_TRACKER_BASE', 'http://127.0.0.1:5519/api').rstrip('/')
# 服务器索引：0=jp
TRACKER_SERVER = int(os.environ.get('GARUPA_TRACKER_SERVER', '0'))
TRACKER_TIMEOUT = int(os.environ.get('GARUPA_TRACKER_TIMEOUT', '30'))

# 短 TTL 缓存：避免前端频繁请求时反复打 tracker 后端
_info_cache = TTLCache(300)
_top_cache = TTLCache(30)


class TrackerError(Exception):
    pass


def _get_json(path, params=None, timeout=TRACKER_TIMEOUT):
    url = f'{GARUPA_TRACKER_BASE}/{path.lstrip("/")}'
    try:
        resp = requests.get(url, params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        raise TrackerError(f'tracker request failed: {url}: {e}') from e
    if resp.status_code != 200:
        raise TrackerError(f'tracker HTTP {resp.status_code}: {url}')
    try:
        return resp.json()
    except Exception as e:
        raise TrackerError(f'tracker invalid json: {url}: {e}') from e


def get_monthly_info(force=False):
    """全部月榜期信息 {id_str: {monthlyRankingName[], assetBundleName, startAt[], endAt[]}}。"""
    if not force:
        cached = _info_cache.get('info')
        if cached is not None:
            return cached
    data = _get_json('monthlyRanking/info.json')
    return _info_cache.set('info', data or {})


def get_monthly_top(monthly_id, force=False):
    """某期月榜的 top 快照 {points:[{time,uid,value}], users:[...]}。"""
    cache_key = ('top', int(monthly_id))
    if not force:
        cached = _top_cache.get(cache_key)
        if cached is not None:
            return cached
    data = _get_json('monthlyRanking/top', {
        'server': TRACKER_SERVER,
        'monthlyId': int(monthly_id),
    })
    if data is None:
        data = {'points': [], 'users': []}
    return _top_cache.set(cache_key, data)
