from __future__ import annotations
import json
from pathlib import Path
from typing import List
from .models import WallpaperItem

APP_NAME = "Mint Wallpaper Studio"
APP_ID = "mint_wallpaper_studio"
CONFIG_DIR = Path.home() / ".config" / APP_ID
CONFIG_FILE = CONFIG_DIR / "config.json"
AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "mint-wallpaper-studio.desktop"
INTERNAL_LIBRARY_DIR = CONFIG_DIR / "library"
PREVIEW_CACHE_DIR = CONFIG_DIR / "cache" / "previews"
DEBUG_LOG_FILE = CONFIG_DIR / "debug.log"

DEFAULTS = {
    "items": [],
    "we_items": [],
    "random_enabled": False,
    "random_interval_minutes": 10,
    "autostart": False,
    "copy_into_library": False,
    "preview_visible": True,
    "window_geometry": "1500x920",
    "filter_mode": "all",
    "source_filter": "all",
    "sort_mode": "name_asc",
    "active_tab": "all",
    "last_selected": "",
    "we_last_sync": 0,
    "we_paths": [],
    "we_enabled": True,
    "last_applied_id": "",
    "last_apply_mode": "single",
    "video_volume": 35,
    "video_mute": True,
    "audio_enabled_monitors": [],
    "show_unsupported_we": False,
    "monitor_sync_mode": True,
    "playlist_target": "synced",
    "preview_autoplay_video": True,
    "start_minimized": False,
    "start_minimized_launch": False,
    "start_minimized_autostart": False,
    "tray_close_notice": True,
    "recent_random_paths": [],
    "selected_monitors": [],
    "close_to_tray": True,
    "pause_on_fullscreen": True,
    "auto_change_mode": "off",
    "auto_change_scope": "workspace",
    "auto_change_per_monitor_enabled": False,
    "auto_change_per_monitor_preference": False,
    "auto_change_per_monitor": {},
}

class ConfigStore:
    def __init__(self) -> None:
        self.data = DEFAULTS.copy()
        self.load()

    def load(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        INTERNAL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                obj = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    self.data.update(obj)
            except Exception:
                pass

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_items(self, key: str = "items") -> List[WallpaperItem]:
        out = []
        for raw in self.data.get(key, []):
            try:
                out.append(WallpaperItem(**raw))
            except Exception:
                continue
        return out

    def set_items(self, items: List[WallpaperItem], key: str = "items") -> None:
        self.data[key] = [i.to_dict() for i in items]
        self.save()
