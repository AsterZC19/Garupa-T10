# backend/app.py
import sys, os
from flask import Flask, send_from_directory
from models import db
from scheduler import init_scheduler

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder=os.path.join(basedir, '..', 'frontend', 'dist'), static_url_path='/assets')

basedir = os.path.abspath(os.path.dirname(__file__))
db_file = os.path.join(basedir, 'data.db')
degrees_db_file = os.path.join(basedir, 'degrees.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_file}"
app.config['SQLALCHEMY_BINDS'] = {
    'degrees': f"sqlite:///{degrees_db_file}"
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# import models so SQLAlchemy sees them
import models  # noqa

# register routes
from routes.events import events_bp
from routes.player import player_bp
from routes.card import card_bp
from routes.degree import degree_bp # New import
app.register_blueprint(events_bp, url_prefix='/api/events')
app.register_blueprint(player_bp, url_prefix='/api/player')
app.register_blueprint(card_bp, url_prefix='/api/cards')
app.register_blueprint(degree_bp, url_prefix='/api/degrees')

# create tables
with app.app_context():
    db.create_all()

# start background scheduler that fetches and updates events
init_scheduler(app)

# serve frontend static (after build)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
