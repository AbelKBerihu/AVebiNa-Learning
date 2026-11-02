@echo off
cd /d "%~dp0"
echo Starting CrossSync Synchronization Server on Windows...
python run_server.py %*
pause
