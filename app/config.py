import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any

DEFAULT_SERVER_URL = "http://127.0.0.1:8765"
DEFAULT_SYNC_TOKEN = "cross-sync-secret-key"
DEFAULT_SYNC_INTERVAL_SEC = 15

def get_app_dir() -> Path:
    """Returns cross-platform directory for application data and settings."""
    env_dir = os.environ.get("AVEBINA_DATA_DIR") or os.environ.get("CROSS_SYNC_DATA_DIR")
    if env_dir:
        path = Path(env_dir)
    elif sys.platform == "win32":
        app_data = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        path = Path(app_data) / "AVebiNaLearning"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "AVebiNaLearning"
    else:
        # Linux and other Unix-like systems
        xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        path = Path(xdg_data) / "AVebiNaLearning"
    
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_recordings_dir() -> Path:
    """Returns dedicated directory where raw meeting and lecture recordings are stored."""
    rec_dir = get_app_dir() / "recordings"
    rec_dir.mkdir(parents=True, exist_ok=True)
    return rec_dir

def open_folder_in_file_manager(folder_path: Path):
    """Opens folder in native operating system file manager (Windows Explorer, Linux Nautilus/Dolphin, Mac Finder)."""
    p = str(folder_path)
    if sys.platform == "win32":
        os.startfile(p)
    elif sys.platform == "darwin":
        subprocess.run(["open", p], check=False)
    else:
        subprocess.run(["xdg-open", p], check=False)

def get_db_path(custom_name: str = "notes.db") -> Path:
    return get_app_dir() / custom_name

def get_settings_path() -> Path:
    return get_app_dir() / "settings.json"

def load_settings() -> Dict[str, Any]:
    """Loads client settings with cross-platform fallback defaults."""
    path = get_settings_path()
    defaults = {
        "server_url": DEFAULT_SERVER_URL,
        "sync_token": DEFAULT_SYNC_TOKEN,
        "auto_sync_interval": DEFAULT_SYNC_INTERVAL_SEC,
        "auto_sync_enabled": True,
        "dark_mode": True,
        "last_sync_timestamp": None,
        "client_id": os.uname().nodename if hasattr(os, "uname") else "client",
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "ollama_endpoint": "http://localhost:11434",
        "active_ai_provider": "gemini"  # "gemini", "openai", "ollama"
    }
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                defaults.update(saved)
        except Exception:
            pass
    return defaults

def save_settings(settings: Dict[str, Any]) -> None:
    path = get_settings_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving settings: {e}", file=sys.stderr)
