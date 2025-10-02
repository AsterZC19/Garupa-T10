import time
from app import app
from scheduler import init_scheduler
from models import db

print("--- Starting Scheduler Process ---")
with app.app_context():
    db.create_all() # Ensure tables are created if they don't exist
    init_scheduler(app)

# Keep the main thread alive so the background scheduler can run
print("Scheduler started. Process will keep running.")
try:
    while True:
        time.sleep(3600)
except (KeyboardInterrupt, SystemExit):
    print("Scheduler process stopped.")
