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
from datetime import datetime
import time

from flask import Blueprint, current_app, jsonify, request

from services.monthly_ingestion import (
    backfill_monthly_history,
    ingest_monthly_master_list,
    refresh_monthly_top,
)
from services.monthly_query_service import (
    clear_monthly_query_cache,
    get_chart_series,
    get_heatmap,
    get_top_players,
)
from services.monthly_heatmap import compute_monthly_heatmap_cache
from services import monthly_repository as repo

monthly_bp = Blueprint('monthly', __name__)

_refresh_executor = ThreadPoolExecutor(max_workers=1)
_last_master_ingest = {'ts': 0}
_last_top_refresh = {}
_last_heatmap_refresh = {}
_last_backfill = {}
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


def _bg_heatmap_refresh(app, monthly_id):
    try:
        with app.app_context():
            app.logger.info(f"Monthly background heatmap refresh for {monthly_id}...")
            compute_monthly_heatmap_cache(monthly_id)
            clear_monthly_query_cache()
    except Exception as e:
        _last_heatmap_refresh[monthly_id] = 0
        app.logger.error(f"Monthly heatmap refresh failed for {monthly_id}: {e}")


def _ensure_master_ingested():
    """master list 缺数据或过期时同步拉取一次。"""
    now = time.time()
    if repo.get_monthly(1) and now - _last_master_ingest['ts'] < MASTER_INGEST_TTL:
        return True
    try:
        count = ingest_monthly_master_list()
        _last_master_ingest['ts'] = now
        clear_monthly_query_cache()
        return count > 0
    except Exception as e:
        current_app.logger.error(f"Monthly master ingest failed: {e}")
        return repo.get_monthly(1) is not None


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
    limit = int(request.args.get('limit', 10))
    period = repo.get_monthly(monthly_id)
    if not period:
        return jsonify({'error': 'monthly not found'}), 404

    now_ms = int(datetime.utcnow().timestamp() * 1000)
    is_active = period.start_at <= now_ms <= period.end_at
    force_refresh = request.args.get('force') == 'true'
    now = time.time()
    last = _last_top_refresh.get(monthly_id, 0)
    if (is_active or force_refresh) and now - last >= REFRESH_COOLDOWN:
        _last_top_refresh[monthly_id] = now
        _refresh_executor.submit(_bg_top_refresh, current_app._get_current_object(), monthly_id)

    # 该期月榜还没有任何历史点 → 同步回填一次（首屏即可见数据），否则后台回填
    if repo.get_monthly_last_stored_ts(monthly_id) == 0:
        if now - _last_backfill.get(monthly_id, 0) >= REFRESH_COOLDOWN:
            _last_backfill[monthly_id] = now
            try:
                current_app.logger.info(f"Monthly synchronous backfill for {monthly_id}...")
                backfill_monthly_history(monthly_id)
                clear_monthly_query_cache()
            except Exception as e:
                current_app.logger.error(f"Monthly synchronous backfill failed for {monthly_id}: {e}")

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
    limit = int(request.args.get('limit', 10))
    hours = int(request.args.get('hours', 48))
    uids_raw = request.args.get('uids', '')
    uids = [u for u in uids_raw.split(',') if u] if uids_raw else None

    result = get_heatmap(monthly_id, limit=limit, hours=hours, uids=uids)

    # 缓存为空且月榜进行中/近期结束 → 后台预计算（带冷却，不阻塞响应）
    period = repo.get_monthly(monthly_id)
    if result['ref_ts'] == 0 and period:
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        worthwhile = (
            period.start_at <= now_ms <= period.end_at
            or (period.end_at > 0 and 0 < (now_ms - period.end_at) <= 7 * 24 * 3600 * 1000)
        )
        if worthwhile:
            now = time.time()
            if now - _last_heatmap_refresh.get(monthly_id, 0) >= REFRESH_COOLDOWN:
                _last_heatmap_refresh[monthly_id] = now
                _refresh_executor.submit(_bg_heatmap_refresh, current_app._get_current_object(), monthly_id)

    return jsonify(result)
