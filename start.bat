@echo off
ECHO Starting server processes...

REM Navigate to the backend directory
cd backend

REM Start the processes defined in the Procfile
honcho start
