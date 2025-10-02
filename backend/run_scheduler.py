import time
from app import app
from scheduler import init_scheduler

print("--- Starting Scheduler Process ---")
init_scheduler(app)

# Keep the main thread alive so the background scheduler can run
print("Scheduler started. Process will keep running.")
try:
    while True:
        time.sleep(3600)
except (KeyboardInterrupt, SystemExit):
    print("Scheduler process stopped.")
