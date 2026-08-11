# backend/routes/monthly.py
"""月榜（月間ランキング）路由。数据来自 GarupaSpeedTracker 后端
（services/tracker_client.py，其内部使用官方 garupa API 并持有设备签名）。

- GET  /api/monthly/                    → 全部月榜期
- GET  /api/monthly/current             → 当前/最近一期
- GET  /api/monthly/<monthly_id>        → 单期信息（含头图）
- GET  /api/monthly/<monthly_id>/top_players → 月榜 top N（后台刷新）
- GET  /api/monthly/<monthly_id>/chart       → PT 曲线
- GET  /api/monthly/<monthly_id>/heatmap     → 48h 活跃热力图
"""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from flask import Blueprint, current_app, jsonify, request

from services.monthly_ingestion import (
    backfill_monthly_history,
    ingest_monthly_master_list,
    refresh_monthly_top,
)
from services.monthly_query_service import (
    clear_monthly_query_cache,
    clear_monthly_heatmap_cache,
    get_chart_series,
    get_heatmap,
    get_top_players,
)
from services.monthly_heatmap import compute_monthly_heatmap_cache
from services.heatmap_time import HEATMAP_MAX_HOURS
from services.timeutil import now_ms
from services import monthly_repository as repo

monthly_bp = Blueprint('monthly', __name__)

_refresh_executor = ThreadPoolExecutor(max_workers=1)
_last_master_ingest = {'ts': 0}
_last_top_refresh = {}
_last_heatmap_refresh = {}
_last_backfill = {}
_heatmap_recompute_lock = threading.Lock()
REFRESH_COOLDOWN = 30
MASTER_INGEST_TTL = 3600  # master list 每小时刷新一次足够


def _bg_top_refresh(app, monthly_id):
    try:
        with app.app_context():
            app.logger.info(f"Monthly background top refresh for {monthly_id}...")
            refresh_monthly_top(monthly_id)
            clear_monthly_query_cache()
    except Exception as e:
        _last_top_refresh[monthly_id] = 0
        app.logger.error(f"Monthly top refresh failed for {monthly_id}: {e}")


def _bg_backfill(app, monthly_id):
    """后台回填全量历史点。与 _bg_top_refresh 共用单线程 executor，
    串行执行，避免首次加载时与 top 刷新并发写库（IntegrityError / 锁冲突），
    也不阻塞 HTTP 响应。"""
    try:
        with app.app_context():
            app.logger.info(f"Monthly background backfill for {monthly_id}...")
            backfill_monthly_history(monthly_id)
            clear_monthly_query_cache()
    except Exception as e:
        _last_backfill[monthly_id] = 0
        app.logger.error(f"Monthly backfill failed for {monthly_id}: {e}")


def _bg_heatmap_refresh(app, monthly_id):
    try:
        with app.app_context():
            app.logger.info(f"Monthly background heatmap refresh for {monthly_id}...")
            with _heatmap_recompute_lock:
                compute_monthly_heatmap_cache(monthly_id)
            clear_monthly_query_cache()
    except Exception as e:
        _last_heatmap_refresh[monthly_id] = 0
        app.logger.error(f"Monthly heatmap refresh failed for {monthly_id}: {e}")


def _recompute_monthly_heatmap_if_stale(monthly_id):
    """进行中的月榜热力图按需重算：有新快照且缓存未覆盖时，同步重算并清内存缓存。

    快照每分钟一条落库，页面每 2 分钟自动刷新；以「最新快照时间 > 缓存写入时间」
    判断过期，使每次刷新都能拿到最新快照驱动的热力图（不再等整点）。已结束的月榜
    数据冻结，不在此重算（由调度器算到结束小时即可）。重算带锁串行、很快。
    """
    with _heatmap_recompute_lock:
        max_snapshot_ts = repo.get_monthly_last_stored_ts(monthly_id)
        if not max_snapshot_ts:
            return
        cache_updated_at = repo.get_monthly_heatmap_latest_updated_at(monthly_id)
        if cache_updated_at is not None and max_snapshot_ts <= cache_updated_at:
            return  # 缓存已覆盖最新快照，无需重算
        if compute_monthly_heatmap_cache(monthly_id) is not None:
            clear_monthly_heatmap_cache()


def _int_arg(value, default, min_value=None, max_value=None):
    """安全解析 query 参数为 int：非法值回退默认，并夹在 [min_value, max_value] 内，
    避免 '?limit=abc' / '?limit=' 等触发 ValueError → 500。"""
    try:
        val = int(value)
    except (TypeError, ValueError):
        val = default
    if min_value is not None and val < min_value:
        val = min_value
    if max_value is not None and val > max_value:
        val = max_value
    return val


def _ensure_master_ingested():
    """master list 缺数据或过期时同步拉取一次。"""
    now = time.time()
    # 哨兵用「是否已有任意一期」而非 get_monthly(1)：tracker 数据里不一定有
    # monthly_id=1（如新库只从最近几期开始），否则每个请求都会重拉整个 master。
    if repo.count_monthly() > 0 and now - _last_master_ingest['ts'] < MASTER_INGEST_TTL:
        return True
    try:
        count = ingest_monthly_master_list()
        _last_master_ingest['ts'] = now
        clear_monthly_query_cache()
        return count > 0
    except Exception as e:
        current_app.logger.error(f"Monthly master ingest failed: {e}")
        return repo.count_monthly() > 0


@monthly_bp.route('/', methods=['GET'])
def list_monthly():
    _ensure_master_ingested()
    return jsonify([repo.serialize_monthly(p) for p in repo.list_monthly()])


@monthly_bp.route('/current', methods=['GET'])
def current_monthly():
    _ensure_master_ingested()
    period = repo.get_current_or_latest_monthly()
    if not period:
        return jsonify({'error': 'no monthly ranking'}), 404
    return jsonify(repo.serialize_monthly(period))


@monthly_bp.route('/<int:monthly_id>', methods=['GET'])
def get_monthly(monthly_id):
    _ensure_master_ingested()
    period = repo.get_monthly(monthly_id)
    if not period:
        # 尝试从 master list 补拉这一期
        try:
            ingest_monthly_master_list()
            period = repo.get_monthly(monthly_id)
        except Exception as e:
            current_app.logger.error(f"Monthly ingest failed for {monthly_id}: {e}")
    if not period:
        return jsonify({'error': 'monthly not found'}), 404
    return jsonify(repo.serialize_monthly(period))


@monthly_bp.route('/<int:monthly_id>/top_players', methods=['GET'])
def get_monthly_top_players(monthly_id):
    limit = _int_arg(request.args.get('limit'), 10, min_value=1, max_value=50)
    period = repo.get_monthly(monthly_id)
    if not period:
        return jsonify({'error': 'monthly not found'}), 404

    current_time_ms = now_ms()
    is_active = repo.is_monthly_period_active(period, current_time_ms)
    force_refresh = request.args.get('force') == 'true'
    now = time.time()
    last = _last_top_refresh.get(monthly_id, 0)
    if (is_active or force_refresh) and now - last >= REFRESH_COOLDOWN:
        _last_top_refresh[monthly_id] = now
        _refresh_executor.submit(_bg_top_refresh, current_app._get_current_object(), monthly_id)

    # 该期月榜还没有任何历史点 → 后台回填全量历史。回填与 top 刷新共用单线程
    # executor 串行执行（不再在请求线程里同步回填，避免并发写库 + 阻塞响应）。
    if repo.get_monthly_last_stored_ts(monthly_id) == 0:
        if now - _last_backfill.get(monthly_id, 0) >= REFRESH_COOLDOWN:
            _last_backfill[monthly_id] = now
            _refresh_executor.submit(_bg_backfill, current_app._get_current_object(), monthly_id)

    player_data = get_top_players(monthly_id, limit)
    if player_data is None:
        return jsonify({'error': 'monthly not found'}), 404
    return jsonify(player_data)


@monthly_bp.route('/<int:monthly_id>/chart', methods=['GET'])
def get_monthly_chart(monthly_id):
    interval = request.args.get('interval', '15m')
    if not repo.get_monthly(monthly_id):
        return jsonify({'error': 'monthly not found'}), 404
    return jsonify(get_chart_series(monthly_id, interval))


@monthly_bp.route('/<int:monthly_id>/heatmap', methods=['GET'])
def get_monthly_heatmap(monthly_id):
    limit = _int_arg(request.args.get('limit'), 10, min_value=1, max_value=50)
    hours = _int_arg(request.args.get('hours'), 48, min_value=1, max_value=HEATMAP_MAX_HOURS)
    uids_raw = request.args.get('uids', '')
    uids = [u for u in uids_raw.split(',') if u] if uids_raw else None

    # 未知 monthly_id → 404，与 top_players / chart 一致（区别于「尚无缓存数据」的空负载）
    period = repo.get_monthly(monthly_id)
    if not period:
        return jsonify({'error': 'monthly not found'}), 404

    current_time_ms = now_ms()
    # 进行中的月榜：有新快照（逐分钟）就同步重算热力图缓存，页面每次自动刷新
    # 都能看到热力图跟着最新快照更新，不再等整点预计算。
    if repo.is_monthly_period_active(period, current_time_ms):
        _recompute_monthly_heatmap_if_stale(monthly_id)

    result = get_heatmap(monthly_id, limit=limit, hours=hours, uids=uids)

    # 缓存为空且月榜进行中/近期结束 → 后台预计算（带冷却，不阻塞响应）
    if result['ref_ts'] == 0:
        worthwhile = repo.is_monthly_period_active(period, current_time_ms) or (
            period.end_at > 0 and 0 < (current_time_ms - period.end_at) <= 7 * 24 * 3600 * 1000
        )
        if worthwhile:
            now = time.time()
            if now - _last_heatmap_refresh.get(monthly_id, 0) >= REFRESH_COOLDOWN:
                _last_heatmap_refresh[monthly_id] = now
                _refresh_executor.submit(_bg_heatmap_refresh, current_app._get_current_object(), monthly_id)

    return jsonify(result)
