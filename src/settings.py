from __future__ import annotations

import configparser
import logging
from pathlib import Path
from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("noot", "SamuGallo-06"))
CONFIG_PATH = CONFIG_DIR / "noot.ini"

DEFAULTS = {
    "paths": {
        "backup": str(Path.home() / ".local" / "share" / "noot" / "backups"),
        "idevicerestore": "Auto Detect",
    },
    "misc": {
        "ask_udid_confirmation": "true",
        "auto_detect_dfu_devices": "false",
    },
    "ui": {
        "theme": "system",
        "language": "en",
    }
}

LANGS = {
    "en": "English",
    "it": "Italiano",
}

logger = logging.getLogger(__name__)

def load() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read_dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            config.read(CONFIG_PATH, encoding="utf-8")
        except (configparser.Error, UnicodeDecodeError) as e:
            logger.warning("Config file corrotto, uso i default: %s", e)
    return config

def save(config: configparser.ConfigParser) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = CONFIG_PATH.with_suffix(".ini.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        config.write(f)
    tmp_path.replace(CONFIG_PATH) 

def validate(path: Path) -> tuple[str, configparser.ConfigParser | None]:
    cfg = configparser.ConfigParser(interpolation=None)
    try:
        with open(path, encoding="utf-8") as f:
            cfg.read_file(f)
    except configparser.Error as e:
        return f"Syntax error: {e}", None
    except UnicodeDecodeError:
        return "File is not valid UTF-8", None
    else:
        return "SUCCESS", cfg

# --- GETTER ---

def get_backup_directory() -> Path:
    cfg = load()
    return Path(cfg.get("paths", "backup"))

def get_ask_udid_confirmation() -> bool:
    cfg = load()
    return cfg.getboolean("misc", "ask_udid_confirmation")

def get_current_theme() -> str:
    cfg = load()
    return cfg.get("ui", "theme").lower()

def get_current_language() -> str:
    cfg = load()
    return cfg.get("ui", "language").lower()

# --- SETTER ---

def set_current_language(lang_code: str) -> None:
    cfg = load()
    if not cfg.has_section("ui"):
        cfg.add_section("ui")
    cfg.set("ui", "language", str(lang_code))
    save(cfg)

def set_current_theme(theme: str) -> None:
    cfg = load()
    if not cfg.has_section("ui"):
        cfg.add_section("ui")
    cfg.set("ui", "theme", str(theme))
    save(cfg)