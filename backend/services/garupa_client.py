# backend/services/garupa_client.py
"""官方 garupa 游戏 API 客户端（月榜数据源）。

月榜（月間ランキング）数据来自官方游戏 API，而非 Bestdori：
- master list:  GET /api/monthlyranking          → 所有月榜期（id/名称/起止时间/素材名）
- top 榜单:     GET /api/user/{uid}/monthlyranking/{monthlyId}/ranking → top/border 玩家

响应体为 AES-128-CBC 加密（NoPadding）的 protobuf，先解密再按 schema 解析
（schema 见 garupa_protobuf.py，移植自参考项目 StarFreedomX/GarupaSpeedTracker）。

加密 KEY/IV 为 CraftEgg 系列游戏（公主连结 / 邦邦）共用公开常量；设备签名
GARUPA_SIGNATURE 需为已注册的真实设备 UUID（master list 不需要，ranking 需要），
由部署者通过环境变量提供（默认值为公开下载器所用签名，仅保证 master list 可用）。
"""
import os
import time
import uuid

import requests
from Crypto.Cipher import AES

from services.ttl_cache import TTLCache

# 尝试读取 backend/.env（若存在）中的 GARUPA_* 配置
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
except Exception:
    pass

GARUPA_BASE_URL = os.environ.get('GARUPA_BASE_URL', 'https://api.garupa.jp/api').rstrip('/')
GARUPA_AES_KEY = os.environ.get('GARUPA_AES_KEY', 'mikumikulukaluka')
GARUPA_AES_IV = os.environ.get('GARUPA_AES_IV', 'lukalukamikumiku')
# 用于爬取榜单的玩家 UID（任意真实玩家即可；服务器返回 top/border 榜，与请求者无关）
GARUPA_UID = os.environ.get('GARUPA_UID', '105602')
# 设备签名：ranking 接口强制校验。master list 不需要。需替换为真实设备 UUID。
GARUPA_SIGNATURE = os.environ.get('GARUPA_SIGNATURE', '3cde36c1-b431-4458-90cf-469cb0096e0a')
GARUPA_CLIENT_VERSION = os.environ.get('GARUPA_CLIENT_VERSION', '')  # 空则自动检测
GARUPA_FALLBACK_VERSION = os.environ.get('GARUPA_FALLBACK_VERSION', '10.1.4')
GARUPA_UNITY_VERSION = os.environ.get('GARUPA_UNITY_VERSION', '2021.3.39f1')
GARUPA_USER_AGENT = os.environ.get(
    'GARUPA_USER_AGENT',
    'UnityPlayer/2021.3.39f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
)
GARUPA_APPLE_LOOKUP_URL = os.environ.get(
    'GARUPA_APPLE_LOOKUP_URL',
    'https://itunes.apple.com/jp/lookup?bundleId=jp.co.craftegg.band',
)

_TIMEOUT = 30
# 版本缓存：默认 1 小时；426 时强制刷新
_version_cache = TTLCache(3600)
# 上一次 426 自动刷新时间，避免 426 风暴
_last_426_refresh = {'ts': 0}


class GarupaAPIError(Exception):
    pass


class SignatureInvalidError(GarupaAPIError):
    """ranking 接口拒绝当前设备签名（signature invalid.）。"""


def _now_ms():
    return int(time.time() * 1000)


def _base_headers():
    return {
        'User-Agent': GARUPA_USER_AGENT,
        'X-Unity-Version': GARUPA_UNITY_VERSION,
        'X-ClientPlatform': 'Android',
        'X-ClientVersion': get_client_version(),
        'X-Signature': GARUPA_SIGNATURE,
        'Content-Type': 'application/octet-stream',
        'Accept': 'application/octet-stream',
    }


def _cipher():
    key = GARUPA_AES_KEY.encode('utf-8')
    iv = GARUPA_AES_IV.encode('utf-8')
    return AES.new(key, AES.MODE_CBC, iv)


def decrypt_payload(data):
    """AES-128-CBC NoPadding 解密。"""
    return _cipher().decrypt(data)


def _detect_client_version_from_apple():
    """从 App Store 查询当前 JP 客户端版本。"""
    try:
        resp = requests.get(GARUPA_APPLE_LOOKUP_URL, timeout=10)
        data = resp.json()
        results = data.get('results') or []
        if results and results[0].get('version'):
            return results[0]['version']
    except Exception as e:
        print(f"[garupa_client] version lookup failed: {e}")
    return None


def get_client_version(force=False):
    """返回客户端版本：环境变量 > App Store 检测 > 兜底版本。"""
    if GARUPA_CLIENT_VERSION:
        return GARUPA_CLIENT_VERSION
    cached = _version_cache.get('client_version')
    if cached and not force:
        return cached
    version = _detect_client_version_from_apple() or GARUPA_FALLBACK_VERSION
    _version_cache.set('client_version', version)
    return version


def fetch_protobuf(path, require_signature=False, max_retries=2):
    """请求官方 API 并返回解密后的 protobuf 字节。

    - HTTP 426（update required）→ 刷新客户端版本后重试；
    - HTTP 403 且错误为 signature invalid → SignatureInvalidError（仅 ranking 需要签名）。
    """
    url = f'{GARUPA_BASE_URL}/{path.lstrip("/")}'
    headers = _base_headers()

    attempt = 0
    while attempt <= max_retries:
        attempt += 1
        try:
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
        except requests.exceptions.RequestException as e:
            print(f"[garupa_client] request failed: {url}: {e}")
            raise GarupaAPIError(f'garupa request failed: {e}')

        if resp.status_code == 426:
            # 客户端版本过旧：强制刷新一次版本号后重试
            now = time.time()
            if now - _last_426_refresh['ts'] > 60:
                _last_426_refresh['ts'] = now
                get_client_version(force=True)
                headers['X-ClientVersion'] = get_client_version()
                continue
            raise GarupaAPIError('garupa update_required (426) after version refresh')

        if resp.status_code != 200:
            body = b''
            try:
                body = decrypt_payload(resp.content)
            except Exception:
                pass
            text = body.decode('utf-8', errors='replace')
            if require_signature and resp.status_code == 403 and 'signature invalid' in text:
                raise SignatureInvalidError(
                    'garupa signature invalid: GARUPA_SIGNATURE 需要替换为真实设备 UUID'
                )
            raise GarupaAPIError(f'garupa HTTP {resp.status_code}: {text}')

        return decrypt_payload(resp.content)

    raise GarupaAPIError('garupa request exhausted retries')


def get_monthly_master():
    """月榜 master list（无需签名）。返回解密后的 protobuf 字节。"""
    return fetch_protobuf('monthlyranking', require_signature=False)


def get_monthly_ranking(monthly_id):
    """某期月榜的 top/border 榜单（需要有效设备签名）。"""
    path = f'user/{GARUPA_UID}/monthlyranking/{int(monthly_id)}/ranking'
    return fetch_protobuf(path, require_signature=True)


def check_signature_configured():
    """粗略判断是否替换了默认签名（默认签名仅 master list 可用）。"""
    default = '3cde36c1-b431-4458-90cf-469cb0096e0a'
    return os.environ.get('GARUPA_SIGNATURE', default) != default
