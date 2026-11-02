@echo off
cd /d "%~dp0"
cls
echo ==========================================================
echo  CrossSync and LearnEcho Master Launcher (Windows)
echo ==========================================================
echo  1. LearnEcho (Live Meeting and Lecture AI Study Companion)
echo  2. CrossSync (Desktop Notes and Tasks App)
echo  3. Sync Server (Start Cloud / LAN Synchronization Server)
echo  4. Headless CLI (Terminal Note and Task Manager)
echo  5. Run Automated Test Suite
echo  6. Exit
echo ==========================================================
set /p choice="Select option [1-6] (Default: 1): "
if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    echo Launching LearnEcho...
    python run_learner.py
    goto end
)
if "%choice%"=="2" (
    echo Launching CrossSync Notes...
    python main.py
    goto end
)
if "%choice%"=="3" (
    echo Starting Sync Server on 0.0.0.0:8765...
    python run_server.py --host 0.0.0.0 --port 8765
    goto end
)
if "%choice%"=="4" (
    python cli.py list
    pause
    goto end
)
if "%choice%"=="5" (
    python -m unittest discover tests
    pause
    goto end
)
if "%choice%"=="6" (
    exit /b 0
)

python run_learner.py

:end
