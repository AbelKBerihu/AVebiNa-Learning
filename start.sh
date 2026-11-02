#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo " ✦ CrossSync & LearnEcho Master Launcher"
echo "=========================================================="
echo " 1) LearnEcho (Live Meeting & Lecture AI Study Companion)"
echo " 2) CrossSync (Desktop Notes & Tasks App)"
echo " 3) Sync Server (Start Cloud / LAN Synchronization Server)"
echo " 4) Headless CLI (Terminal Note & Task Manager)"
echo " 5) Run Automated Test Suite"
echo " 6) Exit"
echo "=========================================================="
read -p "Select option [1-6] (Default: 1): " choice

choice=${choice:-1}

case "$choice" in
    1)
        echo "Launching LearnEcho..."
        python3 run_learner.py
        ;;
    2)
        echo "Launching CrossSync Notes..."
        python3 main.py
        ;;
    3)
        echo "Starting Sync Server on 0.0.0.0:8765..."
        python3 run_server.py --host 0.0.0.0 --port 8765
        ;;
    4)
        python3 cli.py list
        ;;
    5)
        python3 -m unittest discover tests
        ;;
    6)
        echo "Exiting."
        exit 0
        ;;
    *)
        echo "Invalid selection. Launching LearnEcho by default..."
        python3 run_learner.py
        ;;
esac
