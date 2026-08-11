# backend/models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 统一的时间基准（全项目唯一实现，见 services/timeutil.py）
from services.timeutil import now_ms

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String, unique=True, nullable=False)  # external id (e.g., Bestdori)
    name = db.Column(db.String)
    event_type = db.Column(db.String)
    start_at = db.Column(db.Integer)  # ms since epoch
    end_at = db.Column(db.Integer)    # ms since epoch
    banner_url = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)
    updated_at = db.Column(db.Integer, default=now_ms)

class Score(db.Model):
    __tablename__ = 'scores'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String, db.ForeignKey('events.event_id'), index=True)
    uid = db.Column(db.String, index=True)
    name = db.Column(db.String)
    pt = db.Column(db.Integer)
    rank = db.Column(db.Integer)
    signature = db.Column(db.String, nullable=True)
    updated_at = db.Column(db.Integer, default=now_ms)

    __table_args__ = (db.Index('ix_scores_event_id_pt', "event_id", "pt"), )

class ChartPoint(db.Model):
    __tablename__ = 'chart_points'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String, db.ForeignKey('events.event_id'), index=True)
    uid = db.Column(db.String, index=True)
    name = db.Column(db.String)
    timestamp = db.Column(db.Integer)  # ms
    pt = db.Column(db.Integer)

    __table_args__ = (db.Index('ix_chart_points_event_id_uid_timestamp', "event_id", "uid", "timestamp"), )

class AppState(db.Model):
    __tablename__ = 'app_state'
    __bind_key__ = 'degrees'
    key = db.Column(db.String, primary_key=True)
    value = db.Column(db.String)

class PlayerDegree(db.Model):
    __tablename__ = 'player_degrees'
    __bind_key__ = 'degrees'
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String, index=True)
    event_id = db.Column(db.String, index=True)
    rank = db.Column(db.Integer)
    degree_id = db.Column(db.Integer)

    __table_args__ = (db.Index('ix_player_degrees_uid_event_id', "uid", "event_id"), )

class ChartDataCache(db.Model):
    __tablename__ = 'chart_data_cache'
    event_id = db.Column(db.String, primary_key=True)
    uid = db.Column(db.String, primary_key=True)
    bucket_interval = db.Column(db.String, primary_key=True)  # '15m' or '1h'
    bucket_ts = db.Column(db.Integer, primary_key=True)  # ms
    pt = db.Column(db.Integer)
    name = db.Column(db.String)


class EventHeatmapCache(db.Model):
    """Pre-computed 48h active-heatmap counts for an event's top-10 players.

    由调度器每小时从 Bestdori 拉一次逐分钟榜单、按东京墙钟小时统计「PT 创新高」
    次数后落库；页面读此表即可，不再每次实时请求 Bestdori。counts 为 JSON 数组，
    index 0 最旧、末尾最新（长度 = HEATMAP_MAX_HOURS），ref_ts 为最新格子的
    起始 UTC 毫秒。
    """
    __tablename__ = 'event_heatmap_cache'
    event_id = db.Column(db.String, primary_key=True)
    uid = db.Column(db.String, primary_key=True)
    counts = db.Column(db.Text, nullable=True)   # JSON: list[int]
    ref_ts = db.Column(db.Integer, nullable=True)  # ms, newest hour start (UTC)
    updated_at = db.Column(db.Integer, default=now_ms)


class PlayerScoreHistory(db.Model):
    __tablename__ = 'player_score_history'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String, db.ForeignKey('events.event_id'), index=True)
    uid = db.Column(db.String, index=True)
    name = db.Column(db.String, nullable=True) # New column for player name
    pt = db.Column(db.Integer)
    timestamp = db.Column(db.Integer, index=True) # ms

    __table_args__ = (
        db.Index('ix_player_score_history_event_id_uid_timestamp', "event_id", "uid", "timestamp", unique=True),
        db.Index('ix_player_score_history_event_id_timestamp', "event_id", "timestamp"),
    )


# ---------------------------------------------------------------------------
# 月榜（月間ランキング）数据
# 数据源为 GarupaSpeedTracker 后端（见 services/tracker_client.py），其内部
# 使用官方 garupa API（备用直连客户端见 services/garupa_client.py）。
# ---------------------------------------------------------------------------


class MonthlyRanking(db.Model):
    """一期月榜（自然月）的元信息。monthly_id 即官方接口的 monthlyRankingId。"""
    __tablename__ = 'monthly_rankings'
    id = db.Column(db.Integer, primary_key=True)
    monthly_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String, nullable=True)
    start_at = db.Column(db.Integer, default=0)   # ms
    end_at = db.Column(db.Integer, default=0)     # ms
    banner_url = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)
    updated_at = db.Column(db.Integer, default=now_ms)


class MonthlyScore(db.Model):
    """月榜 top N 玩家最新快照（每次刷新全量替换）。"""
    __tablename__ = 'monthly_scores'
    id = db.Column(db.Integer, primary_key=True)
    monthly_id = db.Column(db.Integer, index=True)
    uid = db.Column(db.String, index=True)
    name = db.Column(db.String, nullable=True)
    pt = db.Column(db.Integer, default=0)
    rank = db.Column(db.Integer, default=0)
    signature = db.Column(db.String, nullable=True)   # introduction
    degree_id = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.Integer, default=now_ms)

    __table_args__ = (db.Index('ix_monthly_scores_monthly_id_pt', "monthly_id", "pt"), )


class MonthlyChartPoint(db.Model):
    """月榜 top 玩家逐次快照（供曲线与热力图使用），按 (monthly_id, uid, timestamp) 去重。"""
    __tablename__ = 'monthly_chart_points'
    id = db.Column(db.Integer, primary_key=True)
    monthly_id = db.Column(db.Integer, index=True)
    uid = db.Column(db.String, index=True)
    name = db.Column(db.String, nullable=True)
    timestamp = db.Column(db.Integer, index=True)  # ms
    pt = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.Index('ix_monthly_chart_points_monthly_uid_ts', "monthly_id", "uid", "timestamp", unique=True),
        db.Index('ix_monthly_chart_points_monthly_ts', "monthly_id", "timestamp"),
    )


class MonthlyHeatmapCache(db.Model):
    """月榜 top N 玩家 48h 活跃热力图缓存（每小时由调度器预计算落库）。"""
    __tablename__ = 'monthly_heatmap_cache'
    monthly_id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String, primary_key=True)
    counts = db.Column(db.Text, nullable=True)      # JSON: list[int]
    ref_ts = db.Column(db.Integer, nullable=True)   # ms, newest hour start (UTC)
    updated_at = db.Column(db.Integer, default=now_ms)
