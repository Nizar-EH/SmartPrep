"""
Configuration locale de l'application (clé API stockée sur la machine
de l'utilisateur uniquement, jamais dans le code).
"""
import json
from pathlib import Path

APP_DIR = Path.home() / ".schoolai"
APP_DIR.mkdir(exist_ok=True)
CONFIG_PATH = APP_DIR / "config.json"


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    current = load_config()
    current.update(data)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)


def get_api_key():
    return load_config().get("gemini_api_key", "")


def set_api_key(key: str):
    save_config({"gemini_api_key": key})
