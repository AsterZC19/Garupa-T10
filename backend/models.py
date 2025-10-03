# backend/models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
from datetime import datetime

def now_ms():
    return int(datetime.utcnow().timestamp() * 1000)

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

class PlayerScoreHistory(db.Model):
    __tablename__ = 'player_score_history'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String, db.ForeignKey('events.event_id'), index=True)
    uid = db.Column(db.String, index=True)
    pt = db.Column(db.Integer)
    timestamp = db.Column(db.Integer, index=True) # ms
