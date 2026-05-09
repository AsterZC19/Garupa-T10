import subprocess
import sys
import signal
import os
import time

# List to keep track of child processes
processes = []

def signal_handler(sig, frame):
    print("\n--- Stopping all services ---")
    for p in processes:
        try:
            if p.poll() is None:  # Process is still running
                print(f"Terminating process {p.pid}...")
                p.terminate()
                # On Windows, terminate() might not be enough for some processes, 
                # but let's try graceful termination first.
        except Exception as e:
            print(f"Error terminating process {p.pid}: {e}")
    
    # Wait a bit for processes to clean up
    time.sleep(1)
    
    for p in processes:
        try:
            if p.poll() is None:
                print(f"Killing process {p.pid}...")
                p.kill()
        except Exception as e:
            print(f"Error killing process {p.pid}: {e}")
            
    print("All services stopped.")
    sys.exit(0)

def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("--- Starting Garupa-T10 Backend Services ---")
    
    # Define commands based on Procfile
    # web: waitress-serve --listen=0.0.0.0:11112 --threads=4 app:app
    # worker: python run_scheduler.py
    
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
    
    # Start Web Server
    print("Starting Web Server (Waitress)...")
    web_cmd = [sys.executable, "-m", "waitress", "--listen=0.0.0.0:11112", "--threads=4", "app:app"]
    web_process = subprocess.Popen(web_cmd, cwd=backend_dir)
    processes.append(web_process)
    
    # Start Scheduler
    print("Starting Scheduler (Worker)...")
    worker_cmd = [sys.executable, "run_scheduler.py"]
    worker_process = subprocess.Popen(worker_cmd, cwd=backend_dir)
    processes.append(worker_process)
    
    print("Services started. Press Ctrl+C to stop.")
    
    # Wait for processes to finish (or signal to interrupt)
    while True:
        time.sleep(1)
        # Check if any process has exited unexpectedly
        for p in processes:
            if p.poll() is not None:
                print(f"Process {p.pid} exited unexpectedly with code {p.returncode}.")
                signal_handler(None, None) # Trigger shutdown

if __name__ == "__main__":
    main()
