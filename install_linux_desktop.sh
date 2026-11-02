#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"

echo "Installing Linux Desktop entries into $APP_DIR..."

cat << EOF > "$APP_DIR/learnecho.desktop"
[Desktop Entry]
Name=LearnEcho AI Study Companion
Comment=Live meeting and lecture AI note-taker, flashcard and quiz generator
Exec=python3 $DIR/run_learner.py
Icon=audio-input-microphone
Terminal=false
Type=Application
Categories=Education;Office;Audio;
EOF

cat << EOF > "$APP_DIR/crosssync.desktop"
[Desktop Entry]
Name=CrossSync Notes & Tasks
Comment=Cross-platform synchronized notes and task manager
Exec=python3 $DIR/main.py
Icon=text-editor
Terminal=false
Type=Application
Categories=Office;Utility;
EOF

chmod +x "$APP_DIR/learnecho.desktop" "$APP_DIR/crosssync.desktop"
echo "✓ LearnEcho and CrossSync have been registered in your Linux Applications menu!"
