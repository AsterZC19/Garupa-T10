# backend/app.py
import sys, os
from flask import Flask, send_from_directory
from models import db

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# frontend_path = '/root/Garupa-T10/frontend/dist' # 绝对路径 
# basedir = os.path.abspath(os.path.dirname(__file__)) 
# app = Flask(__name__, static_folder=frontend_path, static_url_path='/assets')

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
db_file = os.path.join(basedir, 'data.db')
degrees_db_file = os.path.join(basedir, 'degrees.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_file}"
app.config['SQLALCHEMY_BINDS'] = {
    'degrees': f"sqlite:///{degrees_db_file}"
}
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Enable WAL mode for SQLite to improve concurrency
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# import models so SQLAlchemy sees them
import models  # noqa

# register routes
from routes.events import events_bp
from routes.player import player_bp
from routes.card import card_bp
from routes.degree import degree_bp # New import
from routes.statistics import statistics_bp
app.register_blueprint(events_bp, url_prefix='/api/events')
app.register_blueprint(player_bp, url_prefix='/api/player')
app.register_blueprint(card_bp, url_prefix='/api/cards')
app.register_blueprint(degree_bp, url_prefix='/api/degrees')
app.register_blueprint(statistics_bp, url_prefix='/api/events')



# serve frontend static (after build)
# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# def serve(path):
#     if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
#         return send_from_directory(app.static_folder, path)
#     return send_from_directory(app.static_folder, 'index.html')

@app.route('/')
def health():
    return {'status': 'ok', 'message': 'Backend is running'}
