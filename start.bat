@echo off
ECHO Starting server processes with custom runner...

REM Run the Python orchestrator script which handles shutdown signals better on Windows
python run_server.py
