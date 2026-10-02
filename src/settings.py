from __future__ import annotations

import configparser
from pathlib import Path
from platformdirs import user_config_dir

CONFIG_DIR = Path(user_config_dir("noot", "SamuGallo-06"))
CONFIG_PATH = CONFIG_DIR / "noot.ini"

DEFAULTS = {
    "paths": {
        "backup": str(Path.home() / ".local" / "share" / "noot" / "backups"),
        "idevicerestore": "Auto Detect",
    },
    "misc":{
        "ask_udid_confirmation": True,
        "auto_detect_dfu_devices": False,
    },
    "ui": {
        "theme": "system",
        "language": "en",
    }
}

def load() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read_dict(DEFAULTS)  # popola i default prima
    if CONFIG_PATH.exists():
        config.read(CONFIG_PATH)  # sovrascrive con quanto salvato
    return config

def save(config: configparser.ConfigParser) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        config.write(f)
        
def validate(path: Path) -> tuple[str, configparser.ConfigParser | None]:
    cfg = configparser.ConfigParser(interpolation=None)
    try:
        with open(path, encoding="utf-8") as f:
            cfg.read_file(f)
    except configparser.Error as e:
        # MissingSectionHeaderError, DuplicateSectionError,
        # DuplicateOptionError, ParsingError...
        return f"Syntax error: {e}", None
    except UnicodeDecodeError:
        return "File is not valid UTF-8", None
    else:
        return "SUCCESS", cfg
        
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
        
