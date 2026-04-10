from __future__ import annotations
import copy
import os
import signal
import random
import shutil
import shlex
import time
import tempfile
import subprocess
import threading
import hashlib
import queue
import copy
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from typing import List, Optional

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:
    DND_FILES = None
    TkinterDnD = None

try:
    from PIL import Image, ImageTk, ImageDraw
except Exception:
    Image = None
    ImageTk = None
    ImageDraw = None

try:
    import pystray
except Exception:
    pystray = None

try:
    import gi
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3, Gtk, GLib
    APPINDICATOR_BACKEND = "ayatana"
except Exception:
    try:
        import gi
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3, Gtk, GLib
        APPINDICATOR_BACKEND = "appindicator"
    except Exception:
        AppIndicator3 = None
        Gtk = None
        GLib = None
        APPINDICATOR_BACKEND = None

from .config import APP_NAME, AUTOSTART_DIR, AUTOSTART_FILE, ConfigStore, INTERNAL_LIBRARY_DIR, PREVIEW_CACHE_DIR, DEBUG_LOG_FILE
from .controller import WallpaperController, DEBUG_LOG_FILE
from .models import WallpaperItem
from .preview import PIL_AVAILABLE, image_resolution, render_image_preview, render_video_thumbnail, render_image_preview_file, render_video_thumbnail_file, find_html_preview_image
from .utils import classify_media, human_dt, human_size, open_in_file_manager, probe_resolution, scan_paths, list_monitors, command_exists, session_is_x11
from .we_sync import sync_wallpaper_engine, detect_steam_install_type


RUNTIME_DIR = Path(tempfile.gettempdir()) / "mint-wallpaper-studio"
PRIMARY_PID_FILE = RUNTIME_DIR / "primary.pid"
COMMAND_FILE = RUNTIME_DIR / "command.txt"


def simple_input(parent, title: str, prompt: str, initial: str = ""):
    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=Theme.BG if "Theme" in globals() else "#07111f")
    win.geometry("760x280")
    try:
        win.minsize(700, 240)
    except Exception:
        pass
    try:
        win.resizable(False, False)
    except Exception:
        pass

    result = {"value": None}
    frame = ttk.Frame(win, padding=22)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=prompt).pack(anchor="w", pady=(0, 10))

    var = tk.StringVar(value=initial)
    ent = ttk.Entry(frame, textvariable=var, width=84)
    ent.pack(fill="x", pady=(0, 18))
    try:
        ent.focus_set()
        ent.selection_range(0, "end")
        ent.icursor("end")
    except Exception:
        pass

    row = ttk.Frame(frame)
    row.pack(fill="x", pady=(10, 0))

    def ok(event=None):
        result["value"] = var.get().strip()
        win.destroy()

    def cancel(event=None):
        result["value"] = None
        win.destroy()

    ttk.Button(row, text="OK", command=ok).pack(side="right", padx=(0, 10), ipadx=20, ipady=4)
    ttk.Button(row, text="Cancel", command=cancel).pack(side="right", ipadx=16, ipady=4)

    try:
        win.bind("<Return>", ok)
        win.bind("<Escape>", cancel)
    except Exception:
        pass

    try:
        win.transient(parent)
    except Exception:
        pass
    try:
        win.grab_set()
    except Exception:
        pass

    win.update_idletasks()
    try:
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        ww = win.winfo_width()
        wh = win.winfo_height()
        x = px + max(0, (pw - ww) // 2)
        y = py + max(0, (ph - wh) // 2)
        win.geometry(f"+{x}+{y}")
    except Exception:
        pass

    parent.wait_window(win)
    return result["value"]


class Theme:
    BG = "#08111f"
    PANEL = "#0d1b30"
    PANEL_ALT = "#12233d"
    FG = "#eef4ff"
    MUTED = "#9cb3d3"
    ACCENT = "#69a7ff"
    GREEN = "#8af0b5"
    RED = "#ff8f8f"
    ORANGE = "#ffbe6b"
    BORDER = "#2e4468"


class App:
    SORTS = {
        "playlist": "Playlist Order",
    }
    TABS = [
        ("all", "All"),
        ("pictures", "Pictures"),
        ("videos", "Videos"),
        ("html", "HTML"),
        ("applications", "Applications"),
        ("wallpaper_engine", "Wallpaper Engine"),
    ]

    def __init__(self, root: tk.Tk, start_minimized: bool = False, launched_from_autostart: bool = False):
        self.root = root
        self.store = ConfigStore()
        self.controller = WallpaperController()
        self.controller.set_audio_options(
            int(self.store.data.get("video_volume", 35)),
            bool(self.store.data.get("video_mute", True)),
        )
        self.root.title(APP_NAME)
        try:
            self.root.wm_class("mint-wallpaper-studio", "mint-wallpaper-studio")
        except Exception:
            pass
        try:
            self.root.iconname("Mint Wallpaper Studio")
        except Exception:
            pass
        try:
            self.root.wm_class("mint-wallpaper-studio", "MintWallpaperStudio")
        except Exception:
            pass
        try:
            self.root.tk.call("wm", "class", self.root._w, "MintWallpaperStudio")
        except Exception:
            pass
        try:
            self.root.iconname("Mint Wallpaper Studio")
        except Exception:
            pass
        self.root.geometry(self.store.data.get("window_geometry", "1560x940"))
        self.root.minsize(1380, 860)
        self.root.configure(bg=Theme.BG)
        self._ensure_local_desktop_entry()
        self._set_app_icons()
        self._ensure_local_desktop_entry()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        existing_primary = self._read_primary_pid()
        if existing_primary and existing_primary != os.getpid() and self._is_pid_alive(existing_primary):
            self._notify_existing_instance_and_exit()
        self._register_primary_instance()

        self.items: List[WallpaperItem] = self.store.get_items("items")
        self.we_items: List[WallpaperItem] = self.store.get_items("we_items")
        self.filtered: List[WallpaperItem] = []
        self.preview_image = None
        self.preview_tmp = None
        self.random_job = None
        self._blink_on = True
        self._blink_job = None
        self._auto_tick_ms = 1000
        self._auto_elapsed_seconds = 0.0
        self._auto_due_seconds = {}
        self._last_auto_scheduler_ts = time.monotonic()
        self.auto_mode_var = tk.StringVar(value=str(self.store.data.get("auto_change_mode", "off")))
        self.auto_interval_var = tk.IntVar(value=int(self.store.data.get("random_interval_minutes", 10)))
        self.auto_change_scope_var = tk.StringVar(value=str(self.store.data.get("auto_change_scope", "workspace")))

        self.search_var = tk.StringVar()
        self.sort_var = tk.StringVar(value=self._norm(self.store.data.get("sort_mode"), self.SORTS, "name_asc"))
        self.tab_var = tk.StringVar(value=self._norm(self.store.data.get("active_tab"), dict(self.TABS), "all"))
        self.status_var = tk.StringVar(value="Ready")
        self.count_var = tk.StringVar(value="0 items")
        self.preview_enabled = tk.BooleanVar(value=bool(self.store.data.get("preview_visible", True)))
        self.show_unsupported_we = tk.BooleanVar(value=bool(self.store.data.get("show_unsupported_we", False)))
        self.monitor_mode = tk.StringVar(value=str(self.store.data.get("monitor_mode", "shared" if bool(self.store.data.get("monitor_sync_mode", True)) else "per_monitor")))
        self.monitor_sync_mode = tk.BooleanVar(value=(self.monitor_mode.get() != "per_monitor"))
        self.playlist_target = tk.StringVar(value=str(self.store.data.get("playlist_target", "synced")))
        self.preview_autoplay_video = tk.BooleanVar(value=bool(self.store.data.get("preview_autoplay_video", True)))
        launch_min_pref = self.store.data.get("start_minimized_launch", self.store.data.get("start_minimized", False))
        autostart_min_pref = self.store.data.get("start_minimized_autostart", self.store.data.get("start_minimized", False))
        self.start_minimized_launch_pref = tk.BooleanVar(value=bool(launch_min_pref))
        self.start_minimized_autostart_pref = tk.BooleanVar(value=bool(autostart_min_pref))
        self.close_to_tray_pref = tk.BooleanVar(value=bool(self.store.data.get("close_to_tray", True)))
        self.pause_on_fullscreen_pref = tk.BooleanVar(value=bool(self.store.data.get("pause_on_fullscreen", True)))
        self.pause_on_fullscreen_enabled = bool(self.store.data.get("pause_on_fullscreen", True))
        self._last_fullscreen_debug_state = None
        self._fullscreen_monitor_stop = threading.Event()
        self._fullscreen_monitor_thread = None
        self.wallpaper_paused_by_user = False
        self.wallpaper_paused_by_fullscreen = False
        self.tray_icon = None
        self.tray_thread = None
        self.tray_indicator = None
        self.tray_menu_widget = None
        self.tray_status_item = None
        self.tray_now_playing_item = None
        self.tray_pause_item = None
        self.tray_mute_item = None
        self.gtk_loop_thread = None
        self.tray_enabled = AppIndicator3 is not None or (pystray is not None and Image is not None)
        self.tray_backend = "appindicator" if AppIndicator3 is not None else ("pystray" if (pystray is not None and Image is not None) else None)
        self.tray_minimized = False
        self.tray_volume_win = None
        self.preview_video_proc = None
        self.preview_popup = None
        self.preview_popup_frame = None
        self.preview_popup_proc = None
        self.preview_click_path = None
        self.preview_cache_dir = PREVIEW_CACHE_DIR
        self.preview_cache_dir.mkdir(parents=True, exist_ok=True)
        self._preview_queue: queue.Queue = queue.Queue()
        self._preview_request_seq = 0
        self._active_row_iid = None
        self._search_job = None
        self._shutdown = False
        self.monitors = list_monitors()
        self.selected_monitors = tk.StringVar(value="")
        saved_selected = list(self.store.data.get("selected_monitors", []) or [])
        available_names = [self._monitor_display_name(m) for m in self.monitors]
        if not saved_selected:
            saved_selected = list(available_names)
        else:
            saved_selected = [n for n in saved_selected if n in available_names]
            if not saved_selected:
                saved_selected = list(available_names)
        self.store.data["selected_monitors"] = list(saved_selected)
        self._ensure_monitor_audio_defaults()
        try:
            self.controller.set_audio_monitor_enabled(list(self._audio_enabled_monitors()))
        except Exception:
            pass
        if not self.store.data.get("auto_change_monitors"):
            self.store.data["auto_change_monitors"] = list(self._monitor_names())
        self.start_minimized_arg = bool(start_minimized)
        self.launched_from_autostart = bool(launched_from_autostart)

        self._repair_items()
        self._style()
        self._build()
        self.root.after(80, lambda: self._move_window_to_primary(self.root, width=max(1460, self.root.winfo_width()), height=max(900, self.root.winfo_height()), offset_x=18, offset_y=18))
        self._refresh_target_box()
        self.search_var.trace_add("write", self._schedule_search_refresh)
        self.root.after(120, self._process_preview_queue)
        self.root.after(160, self._maybe_cleanup_stale_instances_on_start)
        self.refresh_list()
        self._start_active_blink()
        self.root.after(300, self._restore_last_applied)
        self.root.after(800, self._refresh_runtime_state)
        should_start_minimized = bool(self.start_minimized_arg)
        if self.launched_from_autostart and self.start_minimized_autostart_pref.get():
            should_start_minimized = True
        elif (not self.launched_from_autostart) and self.start_minimized_launch_pref.get():
            should_start_minimized = True
        if should_start_minimized:
            if bool(self.close_to_tray_pref.get()):
                self.root.after(250, self.hide_to_tray)
            else:
                self.root.after(250, self.root.iconify)
        self._update_auto_change_hint()
        self._auto_scheduler_signature_cache = self._auto_scheduler_signature()
        self._start_random_if_enabled()
        if self.tray_enabled:
            try:
                self.root.after(180, self._ensure_tray_icon)
            except Exception:
                pass
        self._debug(f"app init pause_on_fullscreen_enabled={self.pause_on_fullscreen_enabled} session_x11={session_is_x11()}")
        self._start_fullscreen_monitor()


    def _register_primary_instance(self) -> None:
        try:
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            PRIMARY_PID_FILE.write_text(str(os.getpid()))
        except Exception:
            pass
        self.root.after(500, self._poll_external_commands)

    def _read_primary_pid(self) -> int | None:
        try:
            return int((PRIMARY_PID_FILE.read_text() or "").strip())
        except Exception:
            return None

    def _is_pid_alive(self, pid: int | None) -> bool:
        if not pid:
            return False
        try:
            os.kill(int(pid), 0)
            return True
        except Exception:
            return False

    def _notify_existing_instance_and_exit(self) -> None:
        try:
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            COMMAND_FILE.write_text(f"show_refresh\n{time.time()}\n")
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        raise SystemExit(0)

    def _poll_external_commands(self) -> None:
        try:
            if COMMAND_FILE.exists():
                payload = COMMAND_FILE.read_text().strip().splitlines()
                if payload and payload[0].strip() == "show_refresh":
                    try:
                        COMMAND_FILE.unlink()
                    except Exception:
                        pass
                    self._show_from_tray()
                    try:
                        self.refresh_list()
                        self._refresh_target_box()
                    except Exception:
                        pass
                    self.set_status("Refreshed existing window instead of opening a second instance.")
        except Exception:
            pass
        if not getattr(self, "_shutdown", False):
            self.root.after(500, self._poll_external_commands)

    def _peek_desktop_temporarily(self, duration_ms: int = 1300) -> None:
        windows = [self.root, getattr(self, "options_window", None), getattr(self, "preview_popup", None), getattr(self, "tray_volume_win", None)]
        hidden = []
        for win in windows:
            if win is None:
                continue
            try:
                if bool(win.winfo_exists()) and str(win.state()) != "withdrawn":
                    win.withdraw()
                    hidden.append(win)
            except Exception:
                pass
        desktop_toggled = False
        try:
            if command_exists("wmctrl"):
                subprocess.run(["wmctrl", "-k", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                desktop_toggled = True
            elif command_exists("xdotool"):
                subprocess.run(["xdotool", "key", "Super+d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                desktop_toggled = True
        except Exception:
            desktop_toggled = False
        if not hidden and not desktop_toggled:
            return
        def _restore():
            if desktop_toggled:
                try:
                    if command_exists("wmctrl"):
                        subprocess.run(["wmctrl", "-k", "off"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    elif command_exists("xdotool"):
                        subprocess.run(["xdotool", "key", "Super+d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                except Exception:
                    pass
            for win in hidden:
                try:
                    if bool(win.winfo_exists()):
                        win.deiconify()
                except Exception:
                    pass
        self.root.after(max(300, int(duration_ms)), _restore)

    def _tray_menu_peek_begin(self) -> None:
        return
        if getattr(self, "_tray_menu_peek_active", False):
            return
        windows = [self.root, getattr(self, "options_window", None), getattr(self, "preview_popup", None), getattr(self, "tray_volume_win", None)]
        hidden = []
        for win in windows:
            if win is None:
                continue
            try:
                if bool(win.winfo_exists()) and str(win.state()) != "withdrawn":
                    win.withdraw()
                    hidden.append(win)
            except Exception:
                pass
        desktop_toggled = False
        try:
            if command_exists("wmctrl"):
                subprocess.run(["wmctrl", "-k", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                desktop_toggled = True
            elif command_exists("xdotool"):
                subprocess.run(["xdotool", "key", "Super+d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                desktop_toggled = True
        except Exception:
            desktop_toggled = False
        self._tray_menu_peek_hidden = hidden
        self._tray_menu_peek_desktop_toggled = desktop_toggled
        self._tray_menu_peek_active = bool(hidden) or desktop_toggled

    def _tray_menu_peek_end(self) -> None:
        hidden = list(getattr(self, "_tray_menu_peek_hidden", []) or [])
        desktop_toggled = bool(getattr(self, "_tray_menu_peek_desktop_toggled", False))
        self._tray_menu_peek_hidden = []
        self._tray_menu_peek_desktop_toggled = False
        self._tray_menu_peek_active = False
        if desktop_toggled:
            try:
                if command_exists("wmctrl"):
                    subprocess.run(["wmctrl", "-k", "off"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                elif command_exists("xdotool"):
                    subprocess.run(["xdotool", "key", "Super+d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            except Exception:
                pass
        for win in hidden:
            try:
                if bool(win.winfo_exists()):
                    win.deiconify()
            except Exception:
                pass

    def _repair_items(self):
        changed = False
        for seq in (self.items, self.we_items):
            for item in seq:
                if not hasattr(item, "enabled"):
                    item.enabled = (item.media_type not in {"application", "html"})
                    changed = True
                p = Path(item.path)
                if p.exists():
                    try:
                        st = p.stat()
                        if not item.size:
                            item.size = st.st_size
                            changed = True
                        if not item.modified_ts:
                            item.modified_ts = st.st_mtime
                            changed = True
                        if not item.format and p.is_file():
                            item.format = p.suffix.lower().lstrip('.')
                            changed = True
                    except Exception:
                        pass
        if changed:
            self.store.set_items(self.items, "items")
            self.store.set_items(self.we_items, "we_items")

    def _norm(self, value, mapping, fallback):
        value = str(value or "").strip()
        return value if value in mapping else fallback


    def _monitor_display_name(self, mon) -> str:
        if isinstance(mon, dict):
            return str(mon.get("name") or mon.get("id") or mon.get("label") or mon.get("output") or "Monitor")
        return str(getattr(mon, "name", None) or getattr(mon, "id", None) or getattr(mon, "label", None) or getattr(mon, "output", None) or "Monitor")

    def _available_monitor_names(self) -> list[str]:
        return [self._monitor_display_name(m) for m in self.monitors]

    def _is_single_monitor_setup(self) -> bool:
        return len(self._available_monitor_names()) <= 1

    def _enforce_single_monitor_mode(self) -> None:
        if not self._is_single_monitor_setup():
            return
        if hasattr(self, "monitor_mode"):
            self.monitor_mode.set("shared")
        self.monitor_sync_mode.set(True)
        self.playlist_target.set("synced")
        self.store.data["monitor_mode"] = "shared"
        self.store.data["monitor_sync_mode"] = True
        self.store.data["playlist_target"] = "synced"
        only = self._available_monitor_names()
        self.store.data["selected_monitors"] = list(only)
        if hasattr(self, "monitor_mode_box"):
            try:
                self.monitor_mode_box.set("Same on all monitors")
                self.monitor_mode_box.configure(state="disabled")
            except Exception:
                pass

    def _primary_monitor_name(self) -> str:
        for mon in self.monitors:
            if isinstance(mon, dict) and mon.get("primary"):
                return self._monitor_display_name(mon)
        names = self._available_monitor_names()
        return names[0] if names else "default"

    def _ensure_monitor_audio_defaults(self) -> None:
        available = self._available_monitor_names()
        current = self.store.data.get("audio_enabled_monitors")
        if isinstance(current, dict):
            enabled = [name for name, flag in current.items() if flag and name in available]
        else:
            enabled = [name for name in list(current or []) if name in available]
        if not available:
            self.store.data["audio_enabled_monitors"] = []
            return
        if not enabled:
            enabled = [self._primary_monitor_name()]
        self.store.data["audio_enabled_monitors"] = enabled

    def _auto_change_monitor_names(self) -> list[str]:
        available = self._monitor_names()
        raw = list(self.store.data.get("auto_change_monitors", []) or [])
        cleaned = [name for name in raw if name in available]
        if not cleaned:
            cleaned = list(available)
        self.store.data["auto_change_monitors"] = list(cleaned)
        return cleaned

    def _primary_monitor_name(self) -> str:
        for mon in self.monitors:
            if isinstance(mon, dict) and mon.get("primary"):
                return self._monitor_display_name(mon)
        names = self._monitor_names()
        return names[0] if names else "default"

    def _audio_enabled_monitors(self) -> list[str]:
        self._ensure_monitor_audio_defaults()
        available = set(self._available_monitor_names())
        return [name for name in list(self.store.data.get("audio_enabled_monitors", []) or []) if name in available]


    def _primary_monitor_bounds(self) -> tuple[int, int, int, int]:
        for mon in self.monitors:
            if isinstance(mon, dict) and mon.get("primary"):
                return (int(mon.get("x", 0)), int(mon.get("y", 0)), max(1, int(mon.get("width", 0) or 1)), max(1, int(mon.get("height", 0) or 1)))
        if self.monitors:
            mon = self.monitors[0]
            if isinstance(mon, dict):
                return (int(mon.get("x", 0)), int(mon.get("y", 0)), max(1, int(mon.get("width", 0) or 1)), max(1, int(mon.get("height", 0) or 1)))
        return (0, 0, max(1, int(self.root.winfo_screenwidth() or 1600)), max(1, int(self.root.winfo_screenheight() or 900)))

    def _move_window_to_primary(self, win, *, width: int | None = None, height: int | None = None, offset_x: int = 32, offset_y: int = 40) -> None:
        try:
            win.update_idletasks()
            mx, my, mw, mh = self._primary_monitor_bounds()
            ww = int(width or win.winfo_width() or 1200)
            wh = int(height or win.winfo_height() or 800)
            ww = min(ww, mw)
            wh = min(wh, mh)
            x = mx + max(0, min(offset_x, mw - ww))
            y = my + max(0, min(offset_y, mh - wh))
            win.geometry(f"{ww}x{wh}+{x}+{y}")
        except Exception:
            pass



    def _ensure_local_desktop_entry(self):
        try:
            base = Path(__file__).resolve().parent.parent
            src_icon = base / "lmws.png"
            run_path = base / "mint-wallpaper-studio"

            apps_dir = Path.home() / ".local" / "share" / "applications"
            icons_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
            apps_dir.mkdir(parents=True, exist_ok=True)
            icons_dir.mkdir(parents=True, exist_ok=True)

            if src_icon.exists():
                dst_icon = icons_dir / "mint-wallpaper-studio.png"
                try:
                    shutil.copy2(src_icon, dst_icon)
                except Exception:
                    pass

            desktop_file = apps_dir / "mint-wallpaper-studio.desktop"
            content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Mint Wallpaper Studio
Comment=Wallpaper manager for Linux Mint
Exec={run_path}
TryExec={run_path}
Icon=mint-wallpaper-studio
Terminal=false
Categories=Graphics;Utility;
StartupNotify=true
StartupWMClass=MintWallpaperStudio
X-GNOME-WMClass=MintWallpaperStudio
"""
            desktop_file.write_text(content, encoding="utf-8")
        except Exception:
            pass

    def _set_app_icons(self):
        try:
            base = Path(__file__).resolve().parent.parent
        except Exception:
            return
        png_path = base / "lmws.png"
        ico_path = base / "lmws.ico"

        self.header_logo = None
        self._window_icon = None

        if png_path.exists():
            # Prefer Tk-native PNG loading for the visible header logo.
            try:
                self.header_logo = tk.PhotoImage(file=str(png_path))
                try:
                    self.header_logo = self.header_logo.subsample(max(1, self.header_logo.width() // 64), max(1, self.header_logo.height() // 64))
                except Exception:
                    pass
            except Exception:
                self.header_logo = None

            # Use PIL as a fallback / for window icon scaling if available.
            try:
                img = Image.open(png_path).convert("RGBA")
                icon_img = img.copy()
                icon_img.thumbnail((48, 48))
                self._window_icon = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(True, self._window_icon)
                if self.header_logo is None:
                    logo_img = img.copy()
                    logo_img.thumbnail((64, 64))
                    self.header_logo = ImageTk.PhotoImage(logo_img)
            except Exception:
                pass

        if ico_path.exists():
            try:
                self.root.iconbitmap(str(ico_path))
            except Exception:
                pass

    def _style_toplevel(self, win, title=None, geometry=None, modal=False):
        try:
            if title is not None:
                win.title(title)
        except Exception:
            pass
        try:
            if geometry:
                win.geometry(geometry)
        except Exception:
            pass
        try:
            win.configure(bg=Theme.BG)
        except Exception:
            pass
        if modal:
            try:
                win.transient(self.root)
                win.grab_set()
            except Exception:
                pass
        return win

    def _dialog_icon(self, kind: str = "info"):
        icons = {
            "info": ("ℹ", Theme.ACCENT),
            "warning": ("⚠", "#f6c56b"),
            "error": ("✖", "#ff7b7b"),
            "question": ("?", Theme.ACCENT),
            "prompt": ("✎", Theme.ACCENT),
            "success": ("✓", "#7ce2a4"),
        }
        return icons.get(kind, icons["info"])

    def _build_dialog_header(self, parent, title: str, message: str, kind: str = "info", is_long: bool = False):
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="both", expand=True)

        icon_text, icon_color = self._dialog_icon(kind)
        icon_wrap = tk.Frame(
            row,
            bg=Theme.PANEL_ALT,
            highlightbackground=Theme.BORDER,
            highlightthickness=1,
            bd=0,
        )
        icon_wrap.pack(side="left", padx=(0, 14), pady=(2, 0), anchor="n")
        tk.Label(
            icon_wrap,
            text=icon_text,
            bg=Theme.PANEL_ALT,
            fg=icon_color,
            font=("Segoe UI Symbol", 22, "bold"),
            width=3,
            height=2,
        ).pack(padx=6, pady=4)

        text_wrap = ttk.Frame(row, style="Card.TFrame")
        text_wrap.pack(side="left", fill="both", expand=True)
        ttk.Label(text_wrap, text=title, style="TitlePopup.TLabel").pack(anchor="w")
        if is_long:
            body = scrolledtext.ScrolledText(
                text_wrap,
                height=14,
                wrap="word",
                bg=Theme.PANEL_ALT,
                fg=Theme.FG,
                insertbackground=Theme.FG,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=Theme.BORDER,
                font=("Segoe UI", 10),
            )
            body.pack(fill="both", expand=True, pady=(10, 0))
            body.insert("1.0", message)
            body.configure(state="disabled")
            return body
        body = tk.Label(
            text_wrap,
            text=message,
            bg=Theme.PANEL,
            fg=Theme.FG,
            justify="left",
            anchor="w",
            wraplength=620,
            font=("Segoe UI", 11),
        )
        body.pack(anchor="w", fill="x", expand=True, pady=(10, 0))
        return body

    def _dark_messagebox(self, title: str, message: str, kind: str = "info", buttons=("OK",), default=None):
        result = {"value": None}
        win = tk.Toplevel(self.root)
        self.options_window = win
        is_long = (len(message or "") > 420) or ((message or "").count("\n") >= 8)
        width = 940 if is_long else 760
        height = 540 if is_long else 220
        self._style_toplevel(win, title=title, geometry=f"{width}x{height}", modal=True)
        try:
            win.minsize(720 if not is_long else 860, 200 if not is_long else 440)
            win.resizable(False, False)
        except Exception:
            pass

        outer = ttk.Frame(win, style="Card.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        self._build_dialog_header(outer, title, message, kind=kind, is_long=is_long)

        btn_row = ttk.Frame(outer, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(16, 0))

        def choose(val):
            result["value"] = val
            try:
                win.grab_release()
            except Exception:
                pass
            self.options_window = None
            win.destroy()

        for label in reversed(buttons):
            style = "Accent.TButton" if label == default else "TButton"
            ttk.Button(btn_row, text=label, style=style, command=lambda v=label: choose(v)).pack(side="right", padx=(8, 0), ipadx=8, ipady=3)

        win.bind("<Escape>", lambda e: choose(None))
        win.protocol("WM_DELETE_WINDOW", lambda: choose(None))
        self.root.update_idletasks()
        try:
            w = win.winfo_width() or width
            h = win.winfo_height() or height
            x = self.root.winfo_rootx() + max(40, (self.root.winfo_width() - w) // 2)
            y = self.root.winfo_rooty() + max(40, (self.root.winfo_height() - h) // 2)
            win.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass
        win.wait_window()
        return result["value"]

    def _ask_yes_no(self, title: str, message: str) -> bool:
        parent = None
        try:
            ow = getattr(self, "options_window", None)
            if ow is not None and ow.winfo_exists():
                parent = ow
        except Exception:
            parent = None
        if parent is None:
            parent = self.root

        try:
            dlg = tk.Toplevel(parent)
            dlg.title(title)
            dlg.transient(parent)
            dlg.grab_set()
            dlg.attributes("-topmost", True)
            dlg.lift()
            try:
                dlg.focus_force()
            except Exception:
                pass
            is_long = (len(message or "") > 420) or ((message or "").count("\n") >= 8)
            width = 960 if is_long else 780
            height = 540 if is_long else 240
            self._style_toplevel(dlg, title=title, geometry=f"{width}x{height}")
            try:
                dlg.minsize(740 if not is_long else 860, 220 if not is_long else 440)
                dlg.resizable(False, False)
            except Exception:
                pass

            frame = ttk.Frame(dlg, style="Card.TFrame", padding=16)
            frame.pack(fill="both", expand=True)
            self._build_dialog_header(frame, title, message, kind="question", is_long=is_long)

            result = {"value": False}
            btns = ttk.Frame(frame, style="Card.TFrame")
            btns.pack(fill="x", pady=(18, 0))
            ttk.Button(btns, text="No", command=lambda: (result.__setitem__("value", False), dlg.destroy())).pack(side="right", ipadx=8, ipady=3)
            ttk.Button(btns, text="Yes", style="Accent.TButton", command=lambda: (result.__setitem__("value", True), dlg.destroy())).pack(side="right", padx=(0, 10), ipadx=12, ipady=3)

            dlg.update_idletasks()
            try:
                px = parent.winfo_rootx()
                py = parent.winfo_rooty()
                pw = parent.winfo_width()
                ph = parent.winfo_height()
                x = px + max(0, (pw - width) // 2)
                y = py + max(0, (ph - height) // 2)
                dlg.geometry(f"{width}x{height}+{x}+{y}")
            except Exception:
                pass

            dlg.wait_window()
            return bool(result["value"])
        except Exception:
            try:
                return bool(messagebox.askyesno(title, message, parent=parent))
            except Exception:
                return bool(messagebox.askyesno(title, message))
    
    def _show_info(self, title: str, message: str):
        self._dark_messagebox(title, message, kind="info", buttons=("OK",), default="OK")

    def _show_error(self, title: str, message: str):
        self._dark_messagebox(title, message, kind="error", buttons=("OK",), default="OK")

    def _prompt_text(self, title: str, prompt: str, initialvalue: str = ""):
        result = {"value": None}
        win = tk.Toplevel(self.root)
        self._style_toplevel(win, title=title, geometry="720x220", modal=True)
        try:
            win.minsize(680, 210)
            win.resizable(False, False)
        except Exception:
            pass

        outer = ttk.Frame(win, style="Card.TFrame", padding=16)
        outer.pack(fill="both", expand=True)
        self._build_dialog_header(outer, title, prompt, kind="prompt", is_long=False)

        value = tk.StringVar(value=initialvalue)
        entry = ttk.Entry(outer, textvariable=value, width=48)
        entry.pack(fill="x", pady=(12, 0))
        entry.focus_set()
        entry.select_range(0, "end")

        btn_row = ttk.Frame(outer, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(16, 0))

        def submit():
            result["value"] = value.get()
            try:
                win.grab_release()
            except Exception:
                pass
            self.options_window = None
            win.destroy()

        def cancel():
            result["value"] = None
            try:
                win.grab_release()
            except Exception:
                pass
            self.options_window = None
            win.destroy()

        ttk.Button(btn_row, text="Cancel", command=cancel).pack(side="right", padx=(8, 0))
        ttk.Button(btn_row, text="OK", style="Accent.TButton", command=submit).pack(side="right")

        win.bind("<Return>", lambda e: submit())
        win.bind("<Escape>", lambda e: cancel())
        win.protocol("WM_DELETE_WINDOW", cancel)
        self.root.update_idletasks()
        try:
            w = win.winfo_reqwidth()
            h = win.winfo_reqheight()
            x = self.root.winfo_rootx() + max(40, (self.root.winfo_width() - w) // 2)
            y = self.root.winfo_rooty() + max(40, (self.root.winfo_height() - h) // 2)
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass
        win.wait_window()
        return result["value"]

    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        self.root.option_add("*Font", "{Segoe UI} 10")
        self.root.option_add("*TCombobox*Listbox.background", Theme.PANEL_ALT)
        self.root.option_add("*TCombobox*Listbox.foreground", Theme.FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", Theme.ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#06101f")
        self.root.option_add("*Menu.background", Theme.PANEL_ALT)
        self.root.option_add("*Menu.foreground", Theme.FG)
        self.root.option_add("*Menu.activeBackground", Theme.ACCENT)
        self.root.option_add("*Menu.activeForeground", "#06101f")

        s.configure("TFrame", background=Theme.BG)
        s.configure("Card.TFrame", background=Theme.PANEL)
        s.configure("Alt.TFrame", background=Theme.PANEL_ALT)
        s.configure("TPanedwindow", background=Theme.BG)
        s.configure("Sash", background=Theme.BORDER, sashthickness=8)

        s.configure("Title.TLabel", background=Theme.BG, foreground=Theme.FG, font=("Segoe UI", 52, "bold"))
        s.configure("Sub.TLabel", background=Theme.BG, foreground=Theme.MUTED, font=("Segoe UI", 15))
        s.configure("Body.TLabel", background=Theme.PANEL, foreground=Theme.FG, font=("Segoe UI", 11))
        s.configure("Muted.TLabel", background=Theme.PANEL, foreground=Theme.MUTED, font=("Segoe UI", 10))
        s.configure("PanelBody.TLabel", background=Theme.PANEL, foreground=Theme.FG, font=("Segoe UI", 11))
        s.configure("PanelMuted.TLabel", background=Theme.PANEL, foreground=Theme.MUTED, font=("Segoe UI", 10))
        s.configure("TitlePopup.TLabel", background=Theme.PANEL, foreground=Theme.FG, font=("Segoe UI", 15, "bold"))
        s.configure("Popup.TFrame", background=Theme.PANEL)
        s.configure("PopupAlt.TFrame", background=Theme.PANEL_ALT)

        s.configure("TLabelframe",
            background=Theme.PANEL,
            bordercolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            relief="solid",
            borderwidth=1
        )
        s.configure("TLabelframe.Label",
            background=Theme.PANEL,
            foreground=Theme.FG,
            font=("Segoe UI", 11, "bold")
        )

        s.configure("TButton",
            padding=(12, 7),
            font=("Segoe UI", 10, "bold"),
            background=Theme.PANEL_ALT,
            foreground=Theme.FG,
            bordercolor=Theme.BORDER,
            darkcolor=Theme.PANEL_ALT,
            lightcolor=Theme.PANEL_ALT,
            relief="flat",
            focusthickness=0
        )
        s.map("TButton",
            background=[("active", "#18355d"), ("pressed", "#0c1c33"), ("disabled", "#0b1526")],
            foreground=[("disabled", "#6f87aa")],
            bordercolor=[("active", Theme.ACCENT), ("pressed", Theme.ACCENT)]
        )

        s.configure("Accent.TButton",
            background=Theme.ACCENT,
            foreground="#06101f",
            bordercolor="#9dc5ff",
            darkcolor=Theme.ACCENT,
            lightcolor=Theme.ACCENT
        )
        s.map("Accent.TButton",
            background=[("active", "#8cbcff"), ("pressed", "#4e87d9")],
            foreground=[("disabled", "#06101f")],
            bordercolor=[("active", "#c3dcff"), ("pressed", "#9dc5ff")]
        )

        s.configure("Tab.TButton",
            padding=(16, 10),
            font=("Segoe UI", 10, "bold"),
            background=Theme.PANEL_ALT,
            foreground=Theme.FG,
            bordercolor=Theme.BORDER,
            darkcolor=Theme.PANEL_ALT,
            lightcolor=Theme.PANEL_ALT
        )
        s.map("Tab.TButton",
            background=[("active", "#18355d"), ("pressed", "#102746")],
            bordercolor=[("active", Theme.ACCENT)]
        )

        s.configure("TabActive.TButton",
            padding=(16, 10),
            font=("Segoe UI", 10, "bold"),
            background=Theme.ACCENT,
            foreground="#06101f",
            bordercolor="#b8d5ff",
            darkcolor=Theme.ACCENT,
            lightcolor=Theme.ACCENT
        )
        s.map("TabActive.TButton",
            background=[("active", "#7fb6ff"), ("pressed", "#5e97eb")],
            bordercolor=[("active", "#d8e8ff"), ("pressed", "#b8d5ff")]
        )

        s.configure("TCheckbutton",
            background=Theme.PANEL,
            foreground=Theme.FG,
            focuscolor=Theme.PANEL,
            indicatorbackground=Theme.PANEL_ALT,
            indicatorforeground=Theme.FG
        )
        s.map("TCheckbutton",
            background=[("active", Theme.PANEL), ("disabled", Theme.PANEL)],
            foreground=[("disabled", "#6f87aa")]
        )

        s.configure("TRadiobutton",
            background=Theme.PANEL,
            foreground=Theme.FG,
            focuscolor=Theme.PANEL,
            indicatorbackground=Theme.PANEL_ALT,
            indicatorforeground=Theme.FG
        )
        s.map("TRadiobutton",
            background=[("active", Theme.PANEL), ("disabled", Theme.PANEL)],
            foreground=[("disabled", "#6f87aa")]
        )

        s.configure("MWS.TNotebook", background=Theme.BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("MWS.TNotebook.Tab",
            background=Theme.PANEL_ALT,
            foreground=Theme.FG,
            padding=(24, 11),
            font=("Segoe UI", 11, "bold"),
            borderwidth=1,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
            bordercolor=Theme.BORDER,
            focuscolor=Theme.BG
        )
        s.map("MWS.TNotebook.Tab",
            background=[("selected", "#6ea7ff"), ("active", "#18355d"), ("!selected", Theme.PANEL_ALT)],
            foreground=[("selected", Theme.BG), ("active", Theme.FG), ("!selected", Theme.FG)],
            lightcolor=[("selected", Theme.ACCENT), ("active", Theme.BORDER)],
            darkcolor=[("selected", Theme.ACCENT), ("active", Theme.BORDER)],
            bordercolor=[("selected", Theme.ACCENT), ("active", Theme.BORDER)],
            padding=[("selected", (24, 11)), ("!selected", (24, 11))],
            expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))]
        )
        s.configure("PerMonitor.TNotebook", background=Theme.PANEL, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("PerMonitor.TNotebook.Tab",
            background=Theme.PANEL_ALT,
            foreground=Theme.FG,
            padding=(16, 8),
            font=("Segoe UI", 10, "bold"),
            borderwidth=1,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
            bordercolor=Theme.BORDER,
            focuscolor=Theme.PANEL
        )
        s.map("PerMonitor.TNotebook.Tab",
            background=[("selected", Theme.ACCENT), ("active", "#18355d"), ("!selected", Theme.PANEL_ALT)],
            foreground=[("selected", "#06101f"), ("active", Theme.FG), ("!selected", Theme.FG)],
            lightcolor=[("selected", Theme.ACCENT), ("active", Theme.BORDER)],
            darkcolor=[("selected", Theme.ACCENT), ("active", Theme.BORDER)],
            bordercolor=[("selected", Theme.ACCENT), ("active", Theme.BORDER)]
        )
        s.configure("TCheckbutton", padding=(4, 4), font=("Segoe UI", 11), background=Theme.PANEL, foreground=Theme.FG, focuscolor=Theme.PANEL)
        s.map("TCheckbutton", background=[("active", Theme.PANEL), ("disabled", Theme.PANEL)], foreground=[("disabled", "#6f87aa")])
        s.configure("TRadiobutton", padding=(4, 4), font=("Segoe UI", 11), background=Theme.PANEL, foreground=Theme.FG, focuscolor=Theme.PANEL, indicatorbackground=Theme.PANEL_ALT, indicatorforeground=Theme.FG)
        s.map("TRadiobutton", background=[("active", Theme.PANEL), ("disabled", Theme.PANEL)], foreground=[("disabled", "#6f87aa")])
        s.configure("TCombobox", padding=6)

        s.configure("Horizontal.TScale",
            background=Theme.PANEL,
            troughcolor=Theme.PANEL_ALT,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER
        )

        s.configure("TEntry",
            fieldbackground=Theme.PANEL_ALT,
            foreground=Theme.FG,
            insertcolor=Theme.FG,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
            padding=6
        )
        s.map("TEntry", bordercolor=[("focus", Theme.ACCENT)])

        s.configure("TSpinbox",
            fieldbackground=Theme.PANEL_ALT,
            foreground=Theme.FG,
            arrowcolor=Theme.FG,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
            insertcolor=Theme.FG,
            padding=4
        )
        s.map("TSpinbox", bordercolor=[("focus", Theme.ACCENT)])

        s.configure("TCombobox",
            fieldbackground=Theme.PANEL_ALT,
            background=Theme.PANEL_ALT,
            foreground=Theme.FG,
            arrowcolor=Theme.FG,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
            padding=5
        )
        s.map("TCombobox",
            fieldbackground=[("readonly", Theme.PANEL_ALT), ("disabled", "#0b1526")],
            background=[("readonly", Theme.PANEL_ALT), ("active", "#18355d")],
            foreground=[("readonly", Theme.FG), ("disabled", "#6f87aa")],
            bordercolor=[("focus", Theme.ACCENT), ("readonly", Theme.BORDER)]
        )

        s.configure("Treeview", background=Theme.PANEL_ALT, fieldbackground=Theme.PANEL_ALT, foreground=Theme.FG, rowheight=30, borderwidth=0)
        s.configure("Treeview.Heading", background=Theme.PANEL, foreground=Theme.FG, font=("Segoe UI", 10, "bold"))
        s.map("Treeview", background=[("selected", Theme.ACCENT)], foreground=[("selected", "#06101f")])

    def _build(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 6))

        title_wrap = ttk.Frame(header)
        title_wrap.pack(side="left", fill="x", expand=True)

        if getattr(self, "header_logo", None):
            tk.Label(title_wrap, image=self.header_logo, bg=Theme.BG).pack(side="left", padx=(0, 12), pady=(2, 0))

        title_text_wrap = ttk.Frame(title_wrap)
        title_text_wrap.pack(side="left", fill="both", expand=True, pady=(0, 2))
        tk.Label(
            title_text_wrap,
            text=APP_NAME,
            bg=Theme.BG,
            fg=Theme.FG,
            font=("Segoe UI", 28, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            title_text_wrap,
            text="Images, videos, playlists, random switching, and Wallpaper Engine sync.",
            bg=Theme.BG,
            fg=Theme.MUTED,
            font=("Segoe UI", 12),
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        btns = ttk.Frame(header)
        btns.pack(side="right", anchor="n", pady=(6, 0))
        ttk.Button(btns, text="Add Media", command=self.open_add_window, width=12).pack(side="left", padx=4)
        self.we_sync_btn = ttk.Button(btns, text="Wallpaper Engine Sync", command=self.sync_we, width=24)
        self.we_sync_btn.pack(side="left", padx=4)
        ttk.Button(btns, text="Options", command=self.open_options, width=10).pack(side="left", padx=4)

        content = ttk.Panedwindow(outer, orient="horizontal")
        content.pack(fill="both", expand=True, pady=(12, 0))
        self.content = content
        left = ttk.Frame(content, style="Card.TFrame", padding=10)
        right = ttk.Frame(content, style="Card.TFrame", padding=10)
        self.left = left
        self.right = right
        content.add(left, weight=7)
        content.add(right, weight=3)

        tabbar = ttk.Frame(left)
        tabbar.pack(fill="x", pady=(0, 8))
        self.tab_buttons = {}
        for idx, (key, label) in enumerate(self.TABS):
            tabbar.columnconfigure(idx, weight=1)
            btn = ttk.Button(tabbar, text=label, command=lambda k=key: self.set_tab(k))
            btn.grid(row=0, column=idx, sticky="ew", padx=(0, 6 if idx < len(self.TABS) - 1 else 0))
            self.tab_buttons[key] = btn
        self._refresh_tab_buttons()

        actionbar = ttk.Frame(left)
        actionbar.pack(fill="x", pady=(0, 8))
        for _col in range(5):
            actionbar.columnconfigure(_col, weight=1)
        ttk.Button(actionbar, text="Apply", command=self.apply_selected).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(actionbar, text="Random Now", command=self.apply_random).grid(row=0, column=1, sticky="ew", padx=4)
        self.pause_btn = ttk.Button(actionbar, text="Pause Wallpaper", command=self.toggle_wallpaper_pause)
        self.pause_btn.grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(actionbar, text="All On", command=self.enable_all_visible).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(actionbar, text="All Off", command=self.disable_all_visible).grid(row=0, column=4, sticky="ew", padx=(4, 0))

        searchbar = ttk.Frame(left)
        searchbar.pack(fill="x", pady=(0, 8))
        searchbar.columnconfigure(1, weight=1)
        ttk.Label(searchbar, text="Search", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        search = ttk.Entry(searchbar, textvariable=self.search_var, width=30)
        search.grid(row=0, column=1, sticky="ew", padx=(8, 12))

        self.target_label = tk.Label(searchbar, text="Playlist Target", bg=Theme.BG, fg=Theme.FG, font=("Segoe UI", 10, "bold"))
        self.target_label.grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.target_box = ttk.Combobox(searchbar, state="readonly", width=16)
        self.target_box.grid(row=0, column=3, sticky="w", padx=(0, 12))
        self.target_box.bind("<<ComboboxSelected>>", lambda e: self._target_changed())

        self.monitor_mode_label_widget = tk.Label(searchbar, text="Monitor Mode", bg=Theme.BG, fg=Theme.FG, font=("Segoe UI", 10, "bold"))
        self.monitor_mode_label_widget.grid(row=0, column=4, sticky="w", padx=(0, 6))
        self.monitor_mode_box = ttk.Combobox(searchbar, state="readonly", width=27, values=["Same on all monitors", "Different per monitor", "Stretch across monitors"])
        self.monitor_mode_box.grid(row=0, column=5, sticky="e")
        self.monitor_mode_box.set(self._monitor_mode_label())
        self.monitor_mode_box.bind("<<ComboboxSelected>>", lambda e: self._monitor_mode_changed({"Same on all monitors": "shared", "Different per monitor": "per_monitor", "Stretch across monitors": "stretch"}.get(self.monitor_mode_box.get(), "shared")))
        if self._is_single_monitor_setup():
            self._enforce_single_monitor_mode()
        else:
            try:
                self.monitor_mode_box.configure(state="readonly")
            except Exception:
                pass

        tree_wrap = ttk.Frame(left, style="Alt.TFrame")
        tree_wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_wrap, columns=("use", "name", "type", "format", "source", "size"), show="headings", selectmode="extended")
        self.tree.pack(side="left", fill="both", expand=True)
        self.drag_line = tk.Frame(tree_wrap, bg=Theme.ACCENT, height=2)
        yscroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        yscroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=yscroll.set)
        headers = [("use", "Use", 96, "center"), ("name", "Name", 370, "w"), ("type", "Type", 90, "center"), ("format", "Format", 88, "center"), ("source", "Source", 150, "center"), ("size", "Size", 90, "e")]
        for col, title, width, anchor in headers:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.tag_configure("row_even", background="#10213a")
        self.tree.tag_configure("row_odd", background="#0d1b30")
        self.tree.tag_configure("playlist_on", foreground=Theme.GREEN)
        self.tree.tag_configure("playlist_off", foreground=Theme.RED)
        self.tree.tag_configure("unsupported", foreground=Theme.ORANGE)
        self.tree.tag_configure("active_item", background="#295dbe", foreground="#ffffff")
        self.tree.tag_configure("drag_target", background="#1b365d")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<ButtonPress-1>", self._drag_start, add=True)
        self.tree.bind("<B1-Motion>", self._drag_motion, add=True)
        self.tree.bind("<ButtonRelease-1>", self._drag_release, add=True)
        self.tree.bind("<Button-1>", self._on_tree_click, add=True)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<ButtonRelease-3>", self._on_right_click)
        self.tree.bind("<Shift-F10>", self._on_context_key)
        self.tree.bind("<space>", lambda e: self.toggle_selected_playlist())

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self._refresh_context_menu()
        self._update_pause_button()

        footer = ttk.Frame(left)
        footer.pack(fill="x", pady=(6, 0))
        ttk.Label(footer, textvariable=self.count_var, style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Clear Local", command=self.clear_local, width=10).pack(side="right", padx=(4, 0))
        ttk.Button(footer, text="Clear All", command=self.clear_all, width=10).pack(side="right")

        top = ttk.Frame(right)
        top.pack(fill="x")
        self.preview_header = top
        ttk.Label(top, text="Preview", style="Body.TLabel").pack(side="left")
        self.html_debug_btn = ttk.Button(top, text="HTML Debug", command=self._open_html_debug_window)
        self.html_debug_btn.pack(side="right")
        self.html_debug_btn.pack_forget()

        self.preview_frame = ttk.Frame(right, style="Alt.TFrame", padding=10)
        self.preview_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.preview_label = tk.Label(self.preview_frame, bg="#07111f", fg="#d7e7ff", text="Select an item", font=("Segoe UI", 18), cursor="hand2")
        self.preview_label.pack(fill="both", expand=True)
        self.preview_label.bind("<Button-1>", self._on_preview_click)
        self.preview_frame.bind("<Button-1>", self._on_preview_click)
        self.preview_label.bind("<Enter>", self._on_preview_hover_enter)
        self.preview_label.bind("<Leave>", self._on_preview_hover_leave)
        self.preview_frame.bind("<Enter>", self._on_preview_hover_enter)
        self.preview_frame.bind("<Leave>", self._on_preview_hover_leave)

        self.details_frame = ttk.Frame(right, style="Card.TFrame")
        self.details_frame.pack(fill="x", pady=(8, 0))
        details = self.details_frame
        self.detail_vars = {k: tk.StringVar(value="-") for k in ["Name", "Type", "Format", "Size", "Resolution", "Modified", "Source", "Playlist", "Path", "Notes"]}
        for i, key in enumerate(self.detail_vars):
            ttk.Label(details, text=f"{key}:", style="Body.TLabel").grid(row=i, column=0, sticky="nw", padx=(0, 8), pady=2)
            ttk.Label(details, textvariable=self.detail_vars[key], style="Muted.TLabel", wraplength=320, justify="left").grid(row=i, column=1, sticky="w", pady=2)

        self.inspector_card = ttk.Frame(right, style="Card.TFrame")
        self.inspector_card.pack(fill="both", expand=False, pady=(8, 0))
        inspector_card = self.inspector_card
        inspector_head = ttk.Frame(inspector_card, style="Card.TFrame")
        inspector_head.pack(fill="x")
        ttk.Label(inspector_head, text="Scene Inspector", style="Body.TLabel").pack(side="left")
        self.inspector_summary_var = tk.StringVar(value="No Scene/Web metadata selected")
        ttk.Label(inspector_head, textvariable=self.inspector_summary_var, style="Muted.TLabel").pack(side="right")
        self.inspector_text = tk.Text(
            inspector_card, height=13, wrap="word",
            bg="#091524", fg="#d9e8ff", insertbackground="#d9e8ff",
            relief="flat", borderwidth=0
        )
        self.inspector_text.pack(fill="both", expand=True, pady=(6, 0))
        self.inspector_text.configure(state="disabled")

        status = ttk.Frame(self.root, style="Alt.TFrame", padding=(8, 4))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        self.tray_status_var = tk.StringVar(value="Tray ready" if self.tray_enabled else "Tray unavailable")
        self.runtime_state_var = tk.StringVar(value="Status: Ready")
        self.now_playing_var = tk.StringVar(value="Now Playing: Nothing active")
        ttk.Label(status, textvariable=self.tray_status_var, style="Muted.TLabel").pack(side="right")

        if not self.preview_enabled.get():
            self.preview_frame.pack_forget()
            self.details_frame.pack_forget()
            self.inspector_card.pack_forget()

        self._apply_we_visibility()
        self._apply_preview_visibility()

    def _apply_preview_visibility(self):
        visible = bool(self.preview_enabled.get())

        try:
            header_packed = self.preview_header.winfo_manager() == "pack"
        except Exception:
            header_packed = False
        try:
            frame_packed = self.preview_frame.winfo_manager() == "pack"
        except Exception:
            frame_packed = False
        try:
            details_packed = self.details_frame.winfo_manager() == "pack"
        except Exception:
            details_packed = False
        try:
            inspector_packed = self.inspector_card.winfo_manager() == "pack"
        except Exception:
            inspector_packed = False

        if visible:
            try:
                if hasattr(self, "content") and str(self.right) not in self.content.panes():
                    self.content.add(self.right, weight=3)
            except Exception:
                pass
            if hasattr(self, "preview_header") and not header_packed:
                self.preview_header.pack(fill="x")
            if not frame_packed:
                self.preview_frame.pack(fill="both", expand=True, pady=(8, 0))
            if not details_packed:
                self.details_frame.pack(fill="x", pady=(8, 0))
            if not inspector_packed:
                self.inspector_card.pack(fill="both", expand=False, pady=(8, 0))
        else:
            if hasattr(self, "preview_header"):
                try:
                    self.preview_header.pack_forget()
                except Exception:
                    pass
            try:
                self.preview_frame.pack_forget()
            except Exception:
                pass
            try:
                self.details_frame.pack_forget()
            except Exception:
                pass
            try:
                self.inspector_card.pack_forget()
            except Exception:
                pass
            try:
                if hasattr(self, "content") and str(self.right) in self.content.panes():
                    self.content.forget(self.right)
            except Exception:
                pass
            self._close_preview_popup()

    def _apply_we_visibility(self):
        enabled = bool(self.store.data.get("we_enabled", True))
        if hasattr(self, "we_sync_btn"):
            try:
                self.we_sync_btn.configure(state=("normal" if enabled else "disabled"))
            except Exception:
                pass
        if hasattr(self, "tab_buttons") and "wallpaper_engine" in self.tab_buttons:
            btn = self.tab_buttons["wallpaper_engine"]
            try:
                if enabled and not btn.winfo_manager():
                    btn.pack(side="left", padx=(0, 6))
                elif not enabled and btn.winfo_manager():
                    btn.pack_forget()
            except Exception:
                pass
        if not enabled and self.tab_var.get() == "wallpaper_engine":
            self.tab_var.set("all")
            self.store.data["active_tab"] = "all"

    def _sort_changed(self):
        raw = self.sort_box.get().split(" — ", 1)[0].strip()
        if raw not in self.SORTS:
            raw = "name_asc"
        self.sort_var.set(raw)
        self.store.data["sort_mode"] = raw
        self.store.save()
        self.refresh_list()
        if raw == "playlist":
            self.set_status("Sort mode: Playlist Order — drag rows to reorder")
        self.store.data["sort_mode"] = self.sort_var.get()
        self.store.data["show_unsupported_we"] = self.show_unsupported_we.get()
        self.store.data["monitor_sync_mode"] = self.monitor_sync_mode.get()
        self.store.data["playlist_target"] = self.playlist_target.get()
        self.store.data["preview_autoplay_video"] = self.preview_autoplay_video.get()
        self.store.data["start_minimized_launch"] = self.start_minimized_launch_pref.get()
        self.store.data["start_minimized_autostart"] = self.start_minimized_autostart_pref.get()
        self.store.data["start_minimized"] = bool(self.start_minimized_launch_pref.get() or self.start_minimized_autostart_pref.get())
        self.store.save()
        self.refresh_list()


    def _monitor_names(self) -> list[str]:
        return [m.get("name", "default") for m in self.monitors] or ["default"]

    def _monitor_mode_effective(self) -> str:
        mode = str(self.store.data.get("monitor_mode", getattr(self, "monitor_mode", tk.StringVar(value="shared")).get() if hasattr(self, "monitor_mode") else "shared") or "shared")
        if mode not in {"shared", "per_monitor", "stretch"}:
            mode = "shared"
        return mode

    def _monitor_mode_label(self, mode: str | None = None) -> str:
        mode = mode or self._monitor_mode_effective()
        return {
            "shared": "Same on all monitors",
            "per_monitor": "Different per monitor",
            "stretch": "Stretch across monitors",
        }.get(mode, "Same on all monitors")

    def _media_monitor_mode_constraint(self, selected=None):
        selected = selected or self.primary_item()
        current_tab = self.tab_var.get() if hasattr(self, "tab_var") else "all"
        media_type = getattr(selected, "media_type", "") if selected else ""
        if current_tab == "html" or media_type == "html":
            return {
                "forced_mode": "stretch",
                "allowed_modes": ["stretch"],
                "forced_target": "synced",
                "hint": "HTML wallpapers currently only support Stretch across monitors.",
            }
        if current_tab == "applications" or media_type == "application":
            primary = self._primary_monitor_name()
            return {
                "forced_mode": "per_monitor",
                "allowed_modes": ["per_monitor"],
                "forced_target": primary or "synced",
                "hint": f"Applications currently only support the primary monitor ({primary})." if primary else "Applications currently only support the primary monitor.",
            }
        return None

    def _apply_media_monitor_mode_constraint(self, selected=None, persist: bool = True):
        constraint = self._media_monitor_mode_constraint(selected)
        if not constraint:
            return None
        forced_mode = constraint.get("forced_mode") or "shared"
        forced_target = constraint.get("forced_target")
        if hasattr(self, "monitor_mode") and self.monitor_mode.get() != forced_mode:
            self.monitor_mode.set(forced_mode)
        self.monitor_sync_mode.set(forced_mode != "per_monitor")
        if persist:
            self.store.data["monitor_mode"] = forced_mode
            self.store.data["monitor_sync_mode"] = (forced_mode != "per_monitor")
        if forced_target:
            self.playlist_target.set(forced_target)
            if persist:
                self.store.data["playlist_target"] = forced_target
        return constraint

    def _refresh_target_box(self):
        names = self._selected_monitor_names()
        mode = self._monitor_mode_effective()
        selected = self.primary_item()
        constraint = self._apply_media_monitor_mode_constraint(selected, persist=True)
        mode = self._monitor_mode_effective()
        app_context = self.tab_var.get() == "applications" or (selected and getattr(selected, "media_type", "") == "application")
        primary = self._primary_monitor_name()
        if mode == "per_monitor":
            if app_context:
                values = [primary] if primary in names else ([primary] if primary else ([names[0]] if names else []))
            else:
                values = list(names)
        else:
            values = ["synced"]
        labels = [self._friendly_target_label(v) for v in values]
        if hasattr(self, "target_box"):
            self._target_value_map = dict(zip(labels, values))
            self.target_box["values"] = labels
            if mode != "per_monitor":
                cur = "synced"
            elif app_context:
                cur = primary if primary in values else (values[0] if values else "")
            else:
                cur = self.playlist_target.get() or (names[0] if names else "")
                if cur not in values:
                    cur = names[0] if names else ""
            self.playlist_target.set(cur)
            self.store.data["playlist_target"] = cur
            self.target_box.set(self._friendly_target_label(cur))
            try:
                self.target_box.configure(state="readonly" if mode == "per_monitor" else "disabled")
            except Exception:
                pass
            if constraint and hasattr(self, "set_status"):
                try:
                    self.set_status(constraint.get("hint") or "")
                except Exception:
                    pass
            try:
                if mode == "per_monitor":
                    if hasattr(self, "target_label"):
                        self.target_label.grid()
                    if hasattr(self, "target_box"):
                        self.target_box.grid()
                else:
                    if hasattr(self, "target_label"):
                        self.target_label.grid_remove()
                    if hasattr(self, "target_box"):
                        self.target_box.grid_remove()
            except Exception:
                pass
        if self._is_single_monitor_setup():
            mode = "shared"
            self._enforce_single_monitor_mode()
        if hasattr(self, "monitor_mode_box"):
            try:
                self.monitor_mode_box.set(self._monitor_mode_label(mode))
                self.monitor_mode_box.configure(state=("disabled" if self._is_single_monitor_setup() else "readonly"))
            except Exception:
                pass
        self._update_monitor_info()

    def _selected_monitor_names(self) -> list[str]:
        available = self._available_monitor_names()
        raw = self.store.data.get("selected_monitors", None)
        if raw is None:
            cleaned = list(available)
        else:
            cleaned = [n for n in list(raw or []) if n in available]
        self.store.data["selected_monitors"] = list(cleaned)
        return cleaned

    def _update_monitor_info(self):
        names = self._selected_monitor_names()
        mode = self._monitor_mode_effective()
        if hasattr(self, "monitor_info_var"):
            self.monitor_info_var.set(", ".join(names) + f"  •  mode: {self._monitor_mode_label(mode)}")

    def _sync_mode_changed(self):
        mode = "shared" if self.monitor_sync_mode.get() else "per_monitor"
        if hasattr(self, "monitor_mode"):
            self.monitor_mode.set(mode)
        self.store.data["monitor_mode"] = mode
        self.store.data["monitor_sync_mode"] = self.monitor_sync_mode.get()
        if mode != "per_monitor":
            self.playlist_target.set("synced")
            self.store.data["playlist_target"] = "synced"
        self.store.save()
        self._refresh_target_box()
        self.refresh_list()
        if constraint:
            self.set_status(constraint.get("hint") or f"Monitor mode: {self._monitor_mode_label(mode)}")
        else:
            self.set_status(f"Monitor mode: {self._monitor_mode_label(mode)}")

    def _friendly_target_label(self, target: str) -> str:
        if target == "synced":
            mode = self._monitor_mode_effective()
            return {
                "shared": "All monitors",
                "stretch": "Span all monitors",
            }.get(mode, "All monitors")
        return target

    def _trigger_random_refresh_on_monitor_mode_change(self, reason: str = ""):
        try:
            self.root.after_idle(self.apply_random)
            if reason:
                self._debug(f"monitor mode random refresh queued reason={reason!r}")
        except Exception as exc:
            try:
                self._debug(f"monitor mode random refresh queue failed reason={reason!r} error={exc}")
            except Exception:
                pass

    def _monitor_mode_changed(self, mode: str):
        previous_mode = self._monitor_mode_effective()
        constraint = self._media_monitor_mode_constraint(self.primary_item())
        if constraint:
            mode = constraint.get("forced_mode") or mode
        if self._is_single_monitor_setup():
            mode = "shared"
        mode = mode or "shared"
        if mode not in {"shared", "per_monitor", "stretch"}:
            mode = "shared"
        if hasattr(self, "monitor_mode"):
            self.monitor_mode.set(mode)
        sync = mode != "per_monitor"
        self.monitor_sync_mode.set(sync)
        self.store.data["monitor_mode"] = mode
        self.store.data["monitor_sync_mode"] = sync
        if mode != "per_monitor":
            self.playlist_target.set("synced")
            self.store.data["playlist_target"] = "synced"
        self.store.save()
        self._refresh_target_box()
        self.refresh_list()
        self.set_status(f"Monitor mode: {self._monitor_mode_label(mode)}")
        if previous_mode != mode:
            self._trigger_random_refresh_on_monitor_mode_change("main_ui")

    def enable_all_visible(self):
        if not self.filtered:
            self.set_status("Nothing to enable in the current view")
            return
        count = 0
        for item in self.filtered:
            if not getattr(item, "supported", True):
                continue
            self._set_item_enabled_for_target(item, True)
            count += 1
        self._persist_items()
        self.store.save()
        self.refresh_list()
        self.set_status(f"Enabled {count} item(s) for {self._friendly_target_label(self.playlist_target.get() or 'synced')}")

    def disable_all_visible(self):
        if not self.filtered:
            self.set_status("Nothing to disable in the current view")
            return
        count = 0
        for item in self.filtered:
            if not getattr(item, "supported", True):
                continue
            self._set_item_enabled_for_target(item, False)
            count += 1
        self._persist_items()
        self.store.save()
        self.refresh_list()
        self.set_status(f"Disabled {count} item(s) for {self._friendly_target_label(self.playlist_target.get() or 'synced')}")

    def _target_changed(self):
        raw = self.target_box.get().strip()
        value = getattr(self, "_target_value_map", {}).get(raw, raw or "synced")
        self.playlist_target.set(value)
        self.store.data["playlist_target"] = value
        self.store.save()
        self.refresh_list()
        self.set_status(f"Playlist target: {self._friendly_target_label(value)}")

    def _item_enabled_for_target(self, item: WallpaperItem) -> bool:
        if self.monitor_sync_mode.get():
            return bool(getattr(item, "enabled", True))
        target = self.playlist_target.get() or "synced"
        targets = getattr(item, "enabled_targets", None) or {}
        if target == "synced":
            return bool(getattr(item, "enabled", True))
        return bool(targets.get(target, False))

    def _set_item_enabled_for_target(self, item: WallpaperItem, value: bool):
        if self.monitor_sync_mode.get():
            item.enabled = bool(value)
            return
        target = self.playlist_target.get() or "synced"
        if target == "synced":
            item.enabled = bool(value)
            return
        targets = getattr(item, "enabled_targets", None) or {}
        targets[target] = bool(value)
        item.enabled_targets = targets

    def _playlist_sorted_all_items(self) -> List[WallpaperItem]:
        items = list(self.items) + list(self.we_items)
        for idx, item in enumerate(items):
            if not hasattr(item, "playlist_order"):
                item.playlist_order = idx
        items.sort(key=lambda i: (getattr(i, "playlist_order", 0), i.name.lower()))
        return items

    def _renumber_playlist_order(self, ordered_items: List[WallpaperItem]):
        for idx, item in enumerate(ordered_items):
            item.playlist_order = idx
        self._persist_items()
        self.store.save()

    def _move_selected_paths_before(self, selected_paths: List[str], before_path: str | None = None):
        ordered = self._playlist_sorted_all_items()
        selected_set = set(selected_paths)
        moving = [i for i in ordered if i.path in selected_set]
        if not moving:
            return
        remaining = [i for i in ordered if i.path not in selected_set]

        insert_at = len(remaining)
        if before_path:
            for idx, item in enumerate(remaining):
                if item.path == before_path:
                    insert_at = idx
                    break

        new_order = remaining[:insert_at] + moving + remaining[insert_at:]
        self._renumber_playlist_order(new_order)

    def _move_selected_relative(self, delta: int):
        if self.tab_var.get() != "all":
            self.set_status("Please switch to the All playlist tab to change item positions.")
            return
        selected = self.selected_items()
        if not selected:
            return
        if len(selected) != 1:
            self.set_status("Move works only for a single selected item")
            return
        ordered = self._playlist_sorted_all_items()
        paths = [i.path for i in selected]
        positions = [idx for idx, item in enumerate(ordered) if item.path in paths]
        if not positions:
            return
        first = min(positions)
        last = max(positions)

        if delta < 0:
            if first <= 0:
                return
            target_path = ordered[first - 1].path
            self._move_selected_paths_before(paths, target_path)
        else:
            if last >= len(ordered) - 1:
                return
            after_path = ordered[last + 1].path
            remaining = [i for i in ordered if i.path not in set(paths)]
            insert_before = None
            for idx, item in enumerate(remaining):
                if item.path == after_path:
                    if idx + 1 < len(remaining):
                        insert_before = remaining[idx + 1].path
                    break
            self._move_selected_paths_before(paths, insert_before)

        self.refresh_list()
        self._reselect_paths(paths)
        self.set_status(f"Moved {len(paths)} item(s) in Playlist Order")

    def _move_selected_top(self):
        if self.tab_var.get() != "all":
            self.set_status("Please switch to the All playlist tab to change item positions.")
            return
        sel = self.selected_items()
        paths = [i.path for i in sel]
        if not paths:
            return
        if len(sel) != 1:
            self.set_status("Move works only for a single selected item")
            return
        self._move_selected_paths_before(paths, None if not self._playlist_sorted_all_items() else self._playlist_sorted_all_items()[0].path)
        self.refresh_list()
        self._reselect_paths(paths)
        self.set_status(f"Moved {len(paths)} item(s) to top of Playlist Order")

    def _move_selected_bottom(self):
        if self.tab_var.get() != "all":
            self.set_status("Please switch to the All playlist tab to change item positions.")
            return
        sel = self.selected_items()
        paths = [i.path for i in sel]
        if not paths:
            return
        if len(sel) != 1:
            self.set_status("Move works only for a single selected item")
            return
        self._move_selected_paths_before(paths, None)
        self.refresh_list()
        self._reselect_paths(paths)
        self.set_status(f"Moved {len(paths)} item(s) to bottom of Playlist Order")

    def _reselect_paths(self, paths: List[str]):
        self.tree.selection_remove(*self.tree.selection())
        wanted = set(paths)
        first_iid = None
        for iid, item in enumerate(self.filtered):
            if item.path in wanted:
                iid = str(iid)
                self.tree.selection_add(iid)
                if first_iid is None:
                    first_iid = iid
        if first_iid is not None:
            self.tree.focus(first_iid)
            self.tree.see(first_iid)
            self.on_select()



    def _clear_drag_indicator(self):
        self._drag_target_path = None
        self._drag_target_row = None
        self._drag_target_position = None
        if hasattr(self, "drag_line"):
            try:
                self.drag_line.place_forget()
            except Exception:
                pass

    def _show_drag_line(self, row_iid: str | None, position: str | None):
        # Only hide the previous line here. Do not wipe the target path,
        # otherwise drop has no destination when the mouse is released.
        if hasattr(self, "drag_line"):
            try:
                self.drag_line.place_forget()
            except Exception:
                pass
        self._drag_target_row = row_iid
        self._drag_target_position = position
        if row_iid is None or position not in {"before", "after"}:
            return
        try:
            bbox = self.tree.bbox(row_iid)
        except Exception:
            return
        if not bbox:
            return
        x, y, w, h = bbox
        line_y = y - 1 if position == "before" else y + h - 1
        try:
            self.drag_line.place(x=2, y=line_y, width=max(10, self.tree.winfo_width() - 4), height=2)
        except Exception:
            pass

    def _move_selected_single_to_position(self, path: str, before_path: str | None):
        self._move_selected_paths_before([path], before_path)
        self.refresh_list()
        self._reselect_paths([path])

    def _ensure_playlist_sort_for_reorder(self) -> bool:
        return True

    def _drag_start(self, event):
        self._drag_item_path = None
        self._drag_started = False
        self._drag_start_xy = (event.x, event.y)
        self._clear_drag_indicator()

        if event.state & 0x0004 or event.state & 0x0001:
            return

        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col == '#1':
            return

        # In non-All tabs, allow normal click/selection behavior, but do not start drag-reorder.
        if self.tab_var.get() != "all":
            return

        if len(self.tree.selection()) != 1 or row not in self.tree.selection():
            self.tree.selection_set(row)
            self.tree.focus(row)
            self.on_select()

        try:
            item = self.filtered[int(row)]
        except Exception:
            return

        self._drag_item_path = item.path
        self._drag_origin_row = row
        self.set_status(f"Dragging: {item.name}")

    def _drag_motion(self, event):
        if self.tab_var.get() != "all":
            return
        drag_path = getattr(self, "_drag_item_path", None)
        if not drag_path:
            return

        sx, sy = getattr(self, "_drag_start_xy", (event.x, event.y))
        if not self._drag_started:
            if abs(event.x - sx) < 6 and abs(event.y - sy) < 6:
                return
            self._drag_started = True

        row = self.tree.identify_row(event.y)
        if not row:
            self._clear_drag_indicator()
            self._drag_target_position = "end"
            self.set_status("Drop at end of playlist")
            return "break"

        try:
            item = self.filtered[int(row)]
        except Exception:
            return "break"

        bbox = self.tree.bbox(row)
        if not bbox:
            return "break"

        x, y, w, h = bbox
        mid_y = y + h / 2
        position = "before" if event.y < mid_y else "after"

        if item.path == drag_path:
            self._clear_drag_indicator()
            self.set_status(f"Dragging: {item.name}")
            return "break"

        self._drag_target_path = item.path
        self._show_drag_line(row, position)
        if position == "before":
            self.set_status(f"Drop before: {item.name}")
        else:
            self.set_status(f"Drop after: {item.name}")
        return "break"

    def _drag_release(self, event):
        if self.tab_var.get() != "all":
            self._drag_item_path = None
            self._drag_started = False
            self._clear_drag_indicator()
            return
        drag_path = getattr(self, "_drag_item_path", None)
        drag_started = bool(getattr(self, "_drag_started", False))
        target_path = getattr(self, "_drag_target_path", None)
        position = getattr(self, "_drag_target_position", None)

        self._drag_item_path = None
        self._drag_started = False

        if not drag_path or not drag_started:
            self._clear_drag_indicator()
            return

        if position == "end":
            self._move_selected_single_to_position(drag_path, None)
            self._clear_drag_indicator()
            self.set_status("Moved item to end of playlist")
            return "break"

        if not target_path or target_path == drag_path:
            self._clear_drag_indicator()
            return "break"

        before_path = target_path
        if position == "after":
            ordered = self._playlist_sorted_all_items()
            remaining = [i for i in ordered if i.path != drag_path]
            idx = next((n for n, it in enumerate(remaining) if it.path == target_path), None)
            if idx is None or idx + 1 >= len(remaining):
                before_path = None
            else:
                before_path = remaining[idx + 1].path

        self._move_selected_single_to_position(drag_path, before_path)
        self._clear_drag_indicator()
        self.set_status("Playlist item moved")
        return "break"


    def _auto_scope_effective(self) -> str:
        scope = str(self.auto_change_scope_var.get() or "workspace")
        if self.monitor_mode.get() != "per_monitor":
            return "workspace"
        target = self.playlist_target.get() or "synced"
        if scope == "target" and target not in {"", "synced"}:
            return "target"
        if scope == "monitors":
            return "monitors"
        return "workspace"

    def _apply_items_to_monitor_layout(self, items_by_monitor: dict[str, WallpaperItem], source_label: str = "Applied") -> str:
        if not items_by_monitor:
            raise RuntimeError("No monitor items selected.")
        first_item = next(iter(items_by_monitor.values()))
        image_map = {mon: item.path for mon, item in items_by_monitor.items() if item.media_type == "image"}
        video_map = {mon: item.path for mon, item in items_by_monitor.items() if item.media_type == "video"}
        other_items = [item for item in items_by_monitor.values() if item.media_type not in {"image", "video"}]

        if other_items:
            if len(items_by_monitor) > 1:
                raise RuntimeError("HTML and application wallpapers currently cannot be mixed across multiple monitors.")
            method = self.controller.apply(first_item)
            self._save_last_applied(first_item, "single")
            return f"{source_label}: {first_item.name} via {method}"

        parts = []
        if image_map:
            method = self.controller.set_image_multi(image_map, stop_video=False)
            self._save_current_image_monitor_layout(image_map)
            parts.append(f"{len(image_map)} image{'s' if len(image_map) != 1 else ''} via {method}")
        else:
            self._save_current_image_monitor_layout({})

        if video_map:
            method = self.controller.set_video_multi(video_map, audio_enabled_monitors=self._audio_enabled_monitors())
            self._save_current_video_monitor_layout(video_map)
            parts.append(f"{len(video_map)} video{'s' if len(video_map) != 1 else ''} via {method}")
        else:
            self.controller.stop_video()
            self._save_current_video_monitor_layout({})

        self._save_last_applied(first_item, "multi")
        if not parts:
            raise RuntimeError("No supported monitor items selected.")
        return f"{source_label}: " + "; ".join(parts)

    def _build_random_monitor_layout(self) -> dict[str, WallpaperItem]:
        layout: dict[str, WallpaperItem] = {}
        all_media: list[str] = []
        targets = self._auto_change_monitor_names() if self._auto_scope_effective() == "monitors" else self._monitor_names()
        for monitor in targets:
            pool = [i for i in self._playlist_pool_for_target(monitor, supported_only=True) if i.media_type in {"image", "video"}]
            if not pool:
                continue
            item = self._pick_less_repetitive_random(pool)
            if not item:
                continue
            layout[monitor] = item
            all_media.append(item.media_type)
        return layout

    def _build_playlist_monitor_layout(self) -> dict[str, WallpaperItem]:
        layout: dict[str, WallpaperItem] = {}
        all_media: list[str] = []
        recent_multi = dict(self.store.data.get("last_applied_multi", {}) or {})
        targets = self._auto_change_monitor_names() if self._auto_scope_effective() == "monitors" else self._monitor_names()
        for monitor in targets:
            pool = [i for i in self._playlist_pool_for_target(monitor, supported_only=True) if i.media_type in {"image", "video"}]
            if not pool:
                continue
            last_path = str(recent_multi.get(monitor, self._get_last_applied_path()) or "")
            idx = -1
            for n, cur in enumerate(pool):
                if cur.path == last_path:
                    idx = n
                    break
            item = pool[(idx + 1) % len(pool)]
            layout[monitor] = item
            all_media.append(item.media_type)
        return layout

    def _save_last_multi_layout(self, items_by_monitor: dict[str, WallpaperItem]) -> None:
        data = {monitor: item.path for monitor, item in items_by_monitor.items() if getattr(item, "path", "")}
        self.store.data["last_applied_multi"] = data
        if data:
            first = next(iter(items_by_monitor.values()))
            self._save_last_applied(first, "multi")

    def _get_current_image_monitor_layout(self) -> dict[str, str]:
        raw = dict(self.store.data.get("current_image_monitor_layout", {}) or {})
        valid = {}
        for mon in self._monitor_names():
            path = str(raw.get(mon, "") or "")
            if path:
                valid[mon] = path
        return valid

    def _save_current_image_monitor_layout(self, mapping: dict[str, str]) -> None:
        clean = {str(mon): str(path) for mon, path in (mapping or {}).items() if mon and path}
        self.store.data["current_image_monitor_layout"] = clean

    def _get_current_video_monitor_layout(self) -> dict[str, str]:
        raw = dict(self.store.data.get("current_video_monitor_layout", {}) or {})
        valid = {}
        for mon in self._monitor_names():
            path = str(raw.get(mon, "") or "")
            if path:
                valid[mon] = path
        return valid

    def _save_current_video_monitor_layout(self, mapping: dict[str, str]) -> None:
        clean = {str(mon): str(path) for mon, path in (mapping or {}).items() if mon and path}
        self.store.data["current_video_monitor_layout"] = clean

    def _primary_monitor_current_item(self):
        primary = self._primary_monitor_name()
        for mapping_getter in (self._get_current_video_monitor_layout, self._get_current_image_monitor_layout):
            try:
                mapping = mapping_getter() or {}
            except Exception:
                mapping = {}
            path = str(mapping.get(primary, "") or "").strip()
            item = self._find_item_by_path(path)
            if item is not None:
                return item
        current = getattr(self.controller, 'current_item', None)
        if current is not None:
            return current
        return self._find_item_by_path(self._get_last_applied_path())

    def _apply_monitor_mode_change_live(self, previous_mode: str, new_mode: str) -> None:
        previous_mode = str(previous_mode or 'shared')
        new_mode = str(new_mode or 'shared')
        if previous_mode == new_mode:
            return
        item = None
        if previous_mode == 'per_monitor' and new_mode in {'shared', 'stretch'}:
            item = self._primary_monitor_current_item()
        elif new_mode == 'per_monitor':
            item = self._find_item_by_path(self._get_last_applied_path()) or getattr(self.controller, 'current_item', None)
        else:
            item = self._find_item_by_path(self._get_last_applied_path()) or getattr(self.controller, 'current_item', None)
        if item is None:
            return
        try:
            self._apply_item_for_current_monitor_context(item, source_label='Updated monitor mode')
        except Exception:
            pass

    def _schedule_pause_button_refreshes(self) -> None:
        def _refresh_once():
            try:
                if not getattr(self, "root", None):
                    return
                self._update_pause_button()
            except Exception:
                pass
        _refresh_once()
        root = getattr(self, "root", None)
        if root is None:
            return
        for delay in (150, 500, 1200):
            try:
                root.after(delay, _refresh_once)
            except Exception:
                pass

    def _finish_apply_status(self, status: str) -> str:
        self._schedule_pause_button_refreshes()
        return status

    def _apply_item_for_current_monitor_context(self, item: WallpaperItem, source_label: str = "Applied") -> str:
        mode = self.monitor_mode.get()
        target = self.playlist_target.get() or "synced"
        monitors = self._monitor_names()
        self._debug(f"apply current context source={source_label!r} item={getattr(item, 'path', '')!r} media={getattr(item, 'media_type', '')!r} mode={mode!r} target={target!r} monitors={monitors!r}")
        if getattr(item, 'media_type', '') not in {'application', 'html'} and (self.controller.is_app_running() or self.controller.is_html_running()):
            self._debug("apply current context stopping existing application/html runtime before applying new media")
            try:
                self.controller.stop_video()
            except Exception as exc:
                self._debug(f"apply current context stop runtime exception: {exc}")
        if item.media_type == "application":
            primary = self._primary_monitor_name()
            if mode == "per_monitor" and target not in {"", primary}:
                raise RuntimeError(f"Applications currently only work on the primary monitor ({primary}).")
            self.playlist_target.set(primary)
            self.store.data["playlist_target"] = primary
            method = self.controller.set_application(item.path)
            self._save_last_applied(item, "single")
            return self._finish_apply_status(f"{source_label} on {primary}: {item.name} via {method}")
        if mode == "stretch":
            if item.media_type == "image":
                method = self.controller.set_image_stretch(item.path)
                self._save_last_applied(item, "single")
                return self._finish_apply_status(f"{source_label}: {item.name} via {method}")
            method = self.controller.apply(item)
            self._save_last_applied(item, "single")
            return self._finish_apply_status(f"{source_label}: {item.name} via {method}")
        if mode == "shared" and item.media_type == "video" and len(monitors) > 1:
            mapping = {mon: item.path for mon in monitors}
            method = self.controller.set_video_multi(mapping, audio_enabled_monitors=self._audio_enabled_monitors())
            self._save_current_video_monitor_layout(mapping)
            self._save_last_applied(item, "multi")
            return self._finish_apply_status(f"{source_label}: same video on {len(monitors)} monitors via {method}")
        if mode == "per_monitor":
            if target not in {"", "synced"}:
                if item.media_type == "application":
                    primary = self._primary_monitor_name()
                    if target != primary:
                        raise RuntimeError(f"Applications currently only work on the primary monitor ({primary}).")
                    method = self.controller.apply(item)
                    self._save_last_applied(item, "single")
                    return self._finish_apply_status(f"{source_label} on {primary}: {item.name} via {method}")
                if item.media_type == "html":
                    method = self.controller.apply(item)
                    self._save_last_applied(item, "single")
                    return self._finish_apply_status(f"{source_label} from {target} playlist: {item.name} via {method}")
                if item.media_type == "image":
                    image_map = self._get_current_image_monitor_layout()
                    image_map[target] = item.path
                    image_map = {mon: path for mon, path in image_map.items() if mon in monitors}
                    video_map = self._get_current_video_monitor_layout()
                    if target in video_map:
                        video_map.pop(target, None)
                        try:
                            self.controller.stop_video_monitor(target)
                        except Exception:
                            pass
                        self._save_current_video_monitor_layout(video_map)
                    # Re-apply the full current image layout so per-monitor image changes do not
                    # accidentally mirror onto other displays when the wallpaper backend refreshes.
                    method = self.controller.set_image_multi(image_map, stop_video=False)
                    self._save_current_image_monitor_layout(image_map)
                    self._save_last_applied(item, "multi")
                    return self._finish_apply_status(f"{source_label} to {target}: {item.name} via {method}")
                if item.media_type == "video":
                    image_map = self._get_current_image_monitor_layout()
                    if target in image_map:
                        image_map.pop(target, None)
                        self._save_current_image_monitor_layout(image_map)
                    video_map = self._get_current_video_monitor_layout()
                    video_map[target] = item.path
                    video_map = {mon: path for mon, path in video_map.items() if mon in monitors}
                    method = self.controller.set_video_on_monitor(target, item.path, audio_enabled_monitors=self._audio_enabled_monitors())
                    self._save_current_video_monitor_layout(video_map)
                    self._save_last_applied(item, "multi")
                    return self._finish_apply_status(f"{source_label} to {target}: {item.name} via {method}")
                method = self.controller.apply(item)
                self._save_last_applied(item, "single")
                return self._finish_apply_status(f"{source_label} from {target} playlist: {item.name} via {method}")
            if item.media_type == "image":
                method = self.controller.set_image_multi({mon: item.path for mon in monitors})
                self._save_last_applied(item, "multi")
                return self._finish_apply_status(f"{source_label}: mirrored image to {len(monitors)} monitors via {method}")
            if item.media_type == "video":
                mapping = {mon: item.path for mon in monitors}
                method = self.controller.set_video_multi(mapping, audio_enabled_monitors=self._audio_enabled_monitors())
                self._save_current_video_monitor_layout(mapping)
                self._save_last_applied(item, "multi")
                return self._finish_apply_status(f"{source_label}: mirrored video to {len(monitors)} monitors via {method}")
        method = self.controller.apply(item)
        self._save_last_applied(item, "single")
        return self._finish_apply_status(f"{source_label}: {item.name} via {method}")

    def _update_auto_change_hint(self):
        if not hasattr(self, "auto_hint_var"):
            return
        mode = self.auto_mode_var.get()
        if mode == "off":
            self.auto_hint_var.set("Automatic changes are turned off.")
            return
        scope = self._auto_scope_effective()
        if self.monitor_mode.get() == "per_monitor" and scope == "target":
            target = self.playlist_target.get() or "selected display"
            if mode == "playlist":
                self.auto_hint_var.set(f"Playlist order will change only the selected display: {target}.")
            else:
                self.auto_hint_var.set(f"Random mode will change only the selected display: {target}.")
            return
        if self.monitor_mode.get() == "per_monitor" and scope == "monitors":
            chosen = ", ".join(self._auto_change_monitor_names()) or "selected displays"
            if mode == "playlist":
                self.auto_hint_var.set(f"Playlist order will change only these displays: {chosen}.")
            else:
                self.auto_hint_var.set(f"Random mode will change only these displays: {chosen}.")
            return
        if self.monitor_mode.get() == "per_monitor":
            if mode == "playlist":
                self.auto_hint_var.set("Playlist order will rotate all selected displays together.")
            else:
                self.auto_hint_var.set("Random mode will refresh all selected displays together.")
            return
        if mode == "playlist":
            self.auto_hint_var.set("Playlist order will rotate the active shared wallpaper setup.")
        else:
            self.auto_hint_var.set("Random mode will pick from enabled items for the current shared monitor setup.")

    def _schedule_search_refresh(self, *_args):
        if self._search_job:
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.root.after(180, self._run_search_refresh)

    def _run_search_refresh(self):
        self._search_job = None
        self.refresh_list()

    def _cache_key(self, item: WallpaperItem) -> str:
        p = Path(item.path)
        try:
            st = p.stat()
            raw = f"{p}|{st.st_mtime_ns}|{st.st_size}|{item.media_type}|{item.format}"
        except Exception:
            raw = f"{p}|{item.media_type}|{item.format}"
        return hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()

    def _cache_path_for(self, item: WallpaperItem) -> Path:
        return self.preview_cache_dir / f"{self._cache_key(item)}.png"

    def _process_preview_queue(self):
        if self._shutdown:
            return
        try:
            while True:
                kind, req_id, item, payload = self._preview_queue.get_nowait()
                if req_id != self._preview_request_seq:
                    continue
                if kind == 'preview_ready':
                    self._apply_preview_result(item, Path(payload))
                elif kind == 'preview_error':
                    self.clear_preview(str(payload))
        except queue.Empty:
            pass
        self.root.after(120, self._process_preview_queue)

    def _apply_preview_result(self, item: WallpaperItem, img_path: Path):
        max_size = (520, 320)
        try:
            self.preview_image = None
            self.preview_tmp = None
            img_obj = tk.PhotoImage(file=str(img_path))
            try:
                sx = max(1, (img_obj.width() + max_size[0] - 1) // max_size[0])
                sy = max(1, (img_obj.height() + max_size[1] - 1) // max_size[1])
                factor = max(sx, sy)
                if factor > 1:
                    img_obj = img_obj.subsample(factor, factor)
            except Exception:
                pass
            self.preview_image = img_obj
            if item.media_type == 'video':
                self.preview_click_path = item.path
                self.preview_label.configure(image=self.preview_image, text='▶\nClick to preview', compound='center', justify='center', font=('Segoe UI', 24, 'bold'), fg='#ffffff')
            else:
                self.preview_click_path = None
                self.preview_label.configure(image=self.preview_image, text='', compound='center', fg='#d7e7ff', font=('Segoe UI', 18))
            self.set_status(f"Preview loaded: {Path(item.path).name}")
        except Exception as exc:
            self.preview_image = None
            self.clear_preview(f"Preview unavailable\n{type(exc).__name__}")

    def _render_preview_background(self, req_id: int, item: WallpaperItem, hover: bool = False):
        try:
            p = Path(item.path)
            cache_path = self._cache_path_for(item)
            if cache_path.exists() and cache_path.stat().st_size > 0:
                self._preview_queue.put(('preview_ready', req_id, item, str(cache_path)))
                return
            max_size = (520, 320)
            tmp_path = None
            if item.media_type == 'video':
                tmp_path = render_video_thumbnail_file(p, max_size)
                if tmp_path is None and PIL_AVAILABLE:
                    thumb = render_video_thumbnail(p, max_size)
                    if thumb is not None:
                        thumb = self._decorate_video_thumb(thumb, hover=hover)
                        thumb.save(cache_path, format='PNG')
                        self._preview_queue.put(('preview_ready', req_id, item, str(cache_path)))
                        return
            else:
                src = p
                if item.media_type == 'html':
                    src = find_html_preview_image(p) or p
                elif item.media_type == 'application':
                    pp = Path(getattr(item, 'preview_path', '') or '')
                    src = pp if pp.exists() else None
                if src is not None:
                    tmp_path = render_image_preview_file(src, max_size)
                    if tmp_path is None and PIL_AVAILABLE:
                        img = render_image_preview(src, max_size)
                        if img is not None:
                            img.save(cache_path, format='PNG')
                            self._preview_queue.put(('preview_ready', req_id, item, str(cache_path)))
                            return
            if tmp_path is not None:
                src = Path(tmp_path)
                if src != cache_path:
                    try:
                        shutil.copy2(src, cache_path)
                    except Exception:
                        cache_path = src
                self._preview_queue.put(('preview_ready', req_id, item, str(cache_path)))
                return
            msg = 'Preview unavailable' if item.media_type == 'image' else '▶\nClick to preview'
            self._preview_queue.put(('preview_error', req_id, item, msg))
        except Exception as exc:
            self._preview_queue.put(('preview_error', req_id, item, f"Preview unavailable\n{type(exc).__name__}"))

    def _update_active_row_visuals(self):
        if not hasattr(self, 'tree'):
            return
        last_path = self._get_last_applied_path()
        new_active = None
        for iid in self.tree.get_children():
            try:
                item = self.filtered[int(iid)]
            except Exception:
                continue
            values = list(self.tree.item(iid, 'values'))
            if values:
                values[0] = self._active_indicator(item)
                self.tree.item(iid, values=tuple(values))
            tags = list(self.tree.item(iid, 'tags'))
            tags = [t for t in tags if t != 'active_item']
            if item.path == last_path:
                tags.append('active_item')
                new_active = iid
            self.tree.item(iid, tags=tuple(tags))
        self._active_row_iid = new_active

    def _playlist_pool_for_target(self, target: str, supported_only: bool = True) -> list[WallpaperItem]:
        pool = []
        for item in self.all_items():
            if supported_only and not item.supported:
                continue
            if target == "synced":
                if getattr(item, "enabled", True):
                    pool.append(item)
            else:
                targets = getattr(item, "enabled_targets", None) or {}
                if targets.get(target, False):
                    pool.append(item)
        return pool

    def _refresh_tab_buttons(self):
        current = self.tab_var.get()
        for key, btn in self.tab_buttons.items():
            btn.configure(style="TabActive.TButton" if key == current else "Tab.TButton")

    def _start_active_blink(self):
        if self._blink_job:
            try:
                self.root.after_cancel(self._blink_job)
            except Exception:
                pass
        def tick():
            self._blink_on = not self._blink_on
            self._update_active_row_visuals()
            self._blink_job = self.root.after(700, tick)
        self._blink_job = self.root.after(700, tick)

    def _active_indicator(self, item):
        active = getattr(item, "path", "") == self._get_last_applied_path()
        enabled = 'ON' if self._item_enabled_for_target(item) else 'OFF'
        if active:
            if getattr(item, "media_type", "") == "html":
                marker = "🌐"
            elif getattr(item, "media_type", "") == "image":
                marker = "🖼"
            elif getattr(self.controller, "video_paused", False):
                marker = "⏸"
            else:
                marker = "▶" if self._blink_on else " "
            return f"{marker} {enabled}"
        return f"  {enabled}"

    def set_tab(self, key: str):
        self.tab_var.set(key)
        self.store.data["active_tab"] = key
        if key == "applications":
            primary = self._primary_monitor_name()
            if primary:
                self.playlist_target.set(primary)
                self.store.data["playlist_target"] = primary
        self._apply_media_monitor_mode_constraint(self.primary_item(), persist=True)
        self.store.save()
        self._refresh_tab_buttons()
        self._refresh_target_box()
        self.refresh_list()

    def _find_item_by_id(self, item_id: str):
        for item in self.all_items():
            if getattr(item, "id", "") == item_id:
                return item
        return None

    def _find_item_by_path(self, path: str):
        path = str(path or "").strip()
        if not path:
            return None
        for item in self.all_items():
            if getattr(item, "path", "") == path:
                return item
        return None

    def _save_last_applied(self, item, mode: str = "single"):
        self.store.data["last_applied_id"] = getattr(item, "id", "")
        self.store.data["last_applied_path"] = getattr(item, "path", "")
        self.store.data["last_apply_mode"] = mode
        self.store.save()
        self._refresh_runtime_state()


    def _remember_random_pick(self, item: WallpaperItem):
        path = str(getattr(item, "path", "") or "")
        if not path:
            return
        history = list(self.store.data.get("recent_random_paths", []) or [])
        history = [p for p in history if p != path]
        history.insert(0, path)
        pool_size = len(self._playlist_enabled_supported()) or 0
        max_keep = max(6, min(20, pool_size // 3 if pool_size else 6))
        self.store.data["recent_random_paths"] = history[:max_keep]
        self.store.save()

    def _pick_less_repetitive_random(self, pool: list[WallpaperItem]) -> WallpaperItem | None:
        if not pool:
            return None
        if len(pool) == 1:
            return pool[0]

        last_path = self._get_last_applied_path()
        history = list(self.store.data.get("recent_random_paths", []) or [])

        recent_window = max(2, min(len(pool) - 1, max(2, len(pool) // 3)))
        recent_set = set(history[:recent_window])

        candidates = [i for i in pool if i.path != last_path and i.path not in recent_set]
        if not candidates:
            candidates = [i for i in pool if i.path != last_path]
        if not candidates:
            candidates = list(pool)

        return random.choice(candidates)

    def _restore_last_applied(self):
        item_id = str(self.store.data.get("last_applied_id", "") or "").strip()
        last_path = str(self.store.data.get("last_applied_path", "") or "").strip()
        item = self._find_item_by_id(item_id) if item_id else None
        if item is None and last_path:
            for cur in self.all_items():
                if cur.path == last_path:
                    item = cur
                    break
        if not item or not getattr(item, "supported", True):
            return
        p = Path(item.path)
        if not p.exists():
            return
        try:
            self._apply_item_for_current_monitor_context(item, "Restored")
            self.refresh_list()
            self._update_pause_button()
            self.set_status(f"Restored last wallpaper: {item.name}")
        except Exception as exc:
            self.set_status(f"Restore failed: {exc}")

    def all_items(self) -> List[WallpaperItem]:
        if not bool(self.store.data.get("we_enabled", True)):
            return list(self.items)
        return self.items + self.we_items

    def _tab_accepts(self, item: WallpaperItem) -> bool:
        tab = self.tab_var.get()
        if tab == "all":
            return True
        if tab == "pictures":
            return item.media_type == "image"
        if tab == "videos":
            return item.media_type == "video"
        if tab == "html":
            return item.media_type == "html"
        if tab == "applications":
            return item.media_type == "application"
        if tab == "wallpaper_engine":
            return item.source == "wallpaper_engine"
        return True

    def refresh_list(self):
        self._clear_drag_indicator()
        all_items = self.all_items()
        query = self.search_var.get().strip().lower()
        items = []
        for item in all_items:
            if not self._tab_accepts(item):
                continue
            blob = f"{item.name} {item.path} {item.format} {item.source} {item.notes}".lower()
            if query and query not in blob:
                continue
            items.append(item)
        items.sort(key=lambda i: (getattr(i, "playlist_order", 0), i.name.lower()))
        self.filtered = items
        selected_paths = {i.path for i in self.selected_items()} if hasattr(self, 'tree') else set()
        last_path = self._get_last_applied_path()
        self.tree.delete(*self.tree.get_children())
        active_iid = None
        for idx, item in enumerate(items):
            on = self._item_enabled_for_target(item)
            state = self._active_indicator(item)
            values = (state, item.name, item.media_type.title(), item.format.upper() if item.format else "-", item.source.replace("_", " ").title(), human_size(item.size))
            tags = ["row_even" if idx % 2 == 0 else "row_odd"]
            tags.append("playlist_on" if on else "playlist_off")
            if not item.supported:
                tags.append("unsupported")
            if item.path == last_path:
                active_iid = str(idx)
                tags.append("active_item")
            self.tree.insert("", "end", iid=str(idx), values=values, tags=tuple(tags))
            if item.path in selected_paths:
                self.tree.selection_add(str(idx))
        visible = len(items)
        playlist_visible = len([i for i in items if self._item_enabled_for_target(i)])
        playlist_total = len([i for i in all_items if self._item_enabled_for_target(i)])
        self.count_var.set(f"{visible} visible • {playlist_visible} enabled in this tab • {playlist_total} enabled total")
        self._active_row_iid = active_iid
        if items:
            if not self.tree.selection():
                target_iid = active_iid if active_iid is not None else "0"
                self.tree.selection_set(target_iid)
                self.tree.focus(target_iid)
            if active_iid is not None:
                self.tree.see(active_iid)
            self.on_select()
        else:
            self.clear_preview("No matching items")
            self.clear_details()

    def selected_items(self) -> List[WallpaperItem]:
        out = []
        for iid in self.tree.selection():
            try:
                out.append(self.filtered[int(iid)])
            except Exception:
                pass
        return out

    def primary_item(self) -> Optional[WallpaperItem]:
        sel = self.selected_items()
        return sel[0] if sel else None

    def clear_details(self):
        for var in self.detail_vars.values():
            var.set("-")
        self._set_inspector_text("No Scene/Web metadata selected", "")

    def on_select(self):
        item = self.primary_item()
        if not item:
            try:
                self.html_debug_btn.pack_forget()
            except Exception:
                pass
            self._close_preview_popup()
            self.clear_preview("Select an item")
            self.clear_details()
            return
        self.detail_vars["Name"].set(item.name)
        self.detail_vars["Type"].set(item.media_type.title())
        self.detail_vars["Format"].set(item.format.upper() if item.format else "-")
        self.detail_vars["Size"].set(human_size(item.size))
        self.detail_vars["Modified"].set(human_dt(item.modified_ts))
        self.detail_vars["Source"].set(item.source.replace("_", " ").title())
        self.detail_vars["Playlist"].set("Enabled" if self._item_enabled_for_target(item) else "Disabled")
        self.detail_vars["Path"].set(item.path)
        self.detail_vars["Notes"].set(item.notes or "-")
        self._update_scene_inspector(item)
        p = Path(item.path)
        w = h = 0
        if p.exists() and item.supported:
            if item.media_type == "image":
                w, h = image_resolution(p)
            elif item.media_type == "video":
                w, h = probe_resolution(p)
            elif item.media_type == "html":
                hp = find_html_preview_image(p)
                if hp is not None:
                    w, h = image_resolution(hp)
            elif item.media_type == "application":
                pp = Path(getattr(item, "preview_path", "") or "")
                if pp.exists():
                    w, h = image_resolution(pp)
        self.detail_vars["Resolution"].set(f"{w}x{h}" if w and h else "-")
        try:
            if item.media_type == "html":
                self.html_debug_btn.pack(side="right")
            else:
                self.html_debug_btn.pack_forget()
        except Exception:
            pass
        self._close_preview_popup()
        self.update_preview(item)


    def _set_inspector_text(self, summary: str, text: str):
        self.inspector_summary_var.set(summary)
        self.inspector_text.configure(state="normal")
        self.inspector_text.delete("1.0", "end")
        self.inspector_text.insert("1.0", text or "")
        self.inspector_text.configure(state="disabled")

    def _update_scene_inspector(self, item: WallpaperItem):
        props = getattr(item, "scene_properties", None) or {}
        files = getattr(item, "scene_files", None) or []
        if item.source != "wallpaper_engine" or (not props and not files):
            self._set_inspector_text("No Scene/Web metadata selected", "")
            return

        lines = []
        ptype = props.get("project_type") or item.notes or "-"
        lines.append(f"Project type: {ptype}")
        if props.get("title"):
            lines.append(f"Title: {props.get('title')}")
        if props.get("workshopid"):
            lines.append(f"Workshop ID: {props.get('workshopid')}")
        tags = props.get("tags")
        if tags:
            lines.append("Tags: " + ", ".join(map(str, tags)))

        proj_props = props.get("project_properties") or {}
        if proj_props:
            lines.append("")
            lines.append("Project properties:")
            for key, meta in proj_props.items():
                lines.append(f"  - {key}: text={meta.get('text')} type={meta.get('type')} value={meta.get('value')}")

        scene_keys = props.get("scene_top_keys") or []
        if scene_keys:
            lines.append("")
            lines.append("scene.json top-level keys:")
            lines.append("  " + ", ".join(map(str, scene_keys)))

        if files:
            lines.append("")
            lines.append("Files in workshop folder:")
            for name in files[:40]:
                lines.append(f"  - {name}")
            if len(files) > 40:
                lines.append(f"  ... and {len(files)-40} more")

        summary = "Scene/Web inspector loaded" if not item.supported else "Wallpaper Engine metadata loaded"
        self._set_inspector_text(summary, "\n".join(lines))



    def _close_preview_popup(self):
        proc = getattr(self, "preview_popup_proc", None)
        self.preview_popup_proc = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        popup = getattr(self, "preview_popup", None)
        self.preview_popup = None
        self.preview_popup_frame = None
        if popup is not None:
            try:
                popup.grab_release()
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass
        restore = getattr(self, "_preview_restore_grab_to", None)
        self._preview_restore_grab_to = None
        if restore is not None:
            try:
                restore.grab_set()
                restore.lift()
                restore.focus_force()
            except Exception:
                pass

    def _open_preview_popup(self, path: Path, parent=None, restore_grab_to=None):
        self._close_preview_popup()
        host = parent or self.root
        win = tk.Toplevel(host)
        self._style_toplevel(win, title=f"Preview Player - {path.name}", geometry="760x460")
        try:
            win.minsize(560, 320)
        except Exception:
            pass
        try:
            win.transient(host)
        except Exception:
            pass

        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text=path.name, style="Body.TLabel").pack(side="left")
        ttk.Button(top, text="Close", command=self._close_preview_popup).pack(side="right")

        frame = tk.Frame(win, bg="#000000")
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.preview_popup = win
        self.preview_popup_frame = frame
        self._preview_restore_grab_to = restore_grab_to
        win.protocol("WM_DELETE_WINDOW", self._close_preview_popup)
        win.update_idletasks()
        try:
            win.lift()
            win.focus_force()
            win.grab_set()
        except Exception:
            pass

        if not command_exists("mpv"):
            lbl = tk.Label(frame, text="mpv not installed", bg="#000000", fg="#ffffff", font=("Segoe UI", 18, "bold"))
            lbl.pack(fill="both", expand=True)
            return

        wid = frame.winfo_id()
        cmd = [
            "mpv",
            f"--wid={wid}",
            "--loop-file=inf",
            "--mute=yes",
            "--no-osc",
            "--no-input-default-bindings",
            "--keep-open=yes",
            "--panscan=1.0",
            "--really-quiet",
            str(path),
        ]
        try:
            self.preview_popup_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            lbl = tk.Label(frame, text=f"Embedded preview failed\n{type(exc).__name__}", bg="#000000", fg="#ffffff", font=("Segoe UI", 18, "bold"))
            lbl.pack(fill="both", expand=True)

    def _on_preview_hover_enter(self, event=None):
        item = self.primary_item()
        if item and item.media_type == "video":
            self.update_preview(item, hover=True)

    def _on_preview_hover_leave(self, event=None):
        item = self.primary_item()
        if item and item.media_type == "video":
            self.update_preview(item, hover=False)

    def _on_preview_hover_enter(self, event=None):
        if getattr(self, "preview_click_path", None):
            try:
                self.preview_label.configure(fg="#ffe082")
            except Exception:
                pass

    def _on_preview_hover_leave(self, event=None):
        try:
            self.preview_label.configure(fg="#ffffff" if getattr(self, "preview_click_path", None) else "#d7e7ff")
        except Exception:
            pass

    def _close_preview_popup(self):
        proc = getattr(self, "preview_popup_proc", None)
        self.preview_popup_proc = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        popup = getattr(self, "preview_popup", None)
        self.preview_popup = None
        self.preview_popup_frame = None
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    def _open_preview_popup(self, path: Path):
        self._close_preview_popup()
        win = tk.Toplevel(self.root)
        win.title(f"Preview Player - {path.name}")
        win.geometry("680x400")
        win.configure(bg=Theme.BG)
        win.transient(self.root)

        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text=path.name, style="Body.TLabel").pack(side="left")
        ttk.Button(top, text="Close", command=self._close_preview_popup).pack(side="right")

        frame = tk.Frame(win, bg="#000000")
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.preview_popup = win
        self.preview_popup_frame = frame
        win.protocol("WM_DELETE_WINDOW", self._close_preview_popup)
        win.update_idletasks()

        if not command_exists("mpv"):
            lbl = tk.Label(frame, text="mpv not installed", bg="#000000", fg="#ffffff", font=("Segoe UI", 18, "bold"))
            lbl.pack(fill="both", expand=True)
            return

        wid = frame.winfo_id()
        cmd = [
            "mpv",
            f"--wid={wid}",
            "--loop-file=inf",
            "--mute=yes",
            "--no-osc",
            "--no-input-default-bindings",
            "--keep-open=yes",
            "--panscan=1.0",
            "--really-quiet",
            str(path),
        ]
        try:
            self.preview_popup_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            lbl = tk.Label(frame, text=f"Embedded preview failed\n{type(exc).__name__}", bg="#000000", fg="#ffffff", font=("Segoe UI", 18, "bold"))
            lbl.pack(fill="both", expand=True)


    def _open_still_preview_popup(self, image_path: Path, title: str = "Preview", parent=None, restore_grab_to=None):
        host = parent or self.root
        win = tk.Toplevel(host)
        self._style_toplevel(win, title=title, geometry="860x620")
        try:
            win.minsize(640, 420)
        except Exception:
            pass
        try:
            win.transient(host)
        except Exception:
            pass

        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text=title, style="Body.TLabel").pack(side="left")
        ttk.Button(top, text="Close", command=win.destroy).pack(side="right")

        frame = tk.Frame(win, bg="#000000")
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        img_file = render_image_preview_file(image_path, (1200, 900))
        popup_img = {"img": None}
        if img_file is not None and Path(img_file).exists():
            try:
                popup_img["img"] = tk.PhotoImage(file=str(img_file))
                lbl = tk.Label(frame, image=popup_img["img"], bg="#000000")
                lbl.image = popup_img["img"]
                lbl.pack(fill="both", expand=True)
            except Exception:
                tk.Label(frame, text="Preview unavailable", bg="#000000", fg="#ffffff", font=("Segoe UI", 18, "bold")).pack(fill="both", expand=True)
        else:
            tk.Label(frame, text="Preview unavailable", bg="#000000", fg="#ffffff", font=("Segoe UI", 18, "bold")).pack(fill="both", expand=True)

        def _on_close():
            try:
                win.destroy()
            finally:
                if restore_grab_to is not None:
                    try:
                        restore_grab_to.grab_set()
                    except Exception:
                        pass

        win.protocol("WM_DELETE_WINDOW", _on_close)
        try:
            win.lift()
            win.focus_force()
            win.grab_set()
        except Exception:
            pass

    def _on_preview_click(self, event=None):
        path = getattr(self, "preview_click_path", None)
        if not path:
            return
        p = Path(path)
        self._close_preview_popup()
        item = None
        try:
            item = self.primary_item()
        except Exception:
            item = None
        media_type = getattr(item, "media_type", "")
        if media_type == "video":
            self._open_preview_popup(p)
        elif media_type == "html":
            hp = find_html_preview_image(p)
            if hp is not None and Path(hp).exists():
                self._open_still_preview_popup(Path(hp), title=f"HTML Preview - {p.stem}")
            else:
                subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self._open_still_preview_popup(p, title=f"Preview - {p.name}")
        self.set_status(f"Preview popup opened: {p.name}")

    def clear_preview(self, message: str):
        self.preview_click_path = None
        self.preview_image = None
        self.preview_label.configure(image="", text=message, compound="center", fg="#d7e7ff", font=("Segoe UI", 18))

    def _decorate_video_thumb(self, img, hover: bool = False):
        if ImageDraw is None or img is None:
            return img
        try:
            canvas = img.copy().convert("RGBA")
            draw = ImageDraw.Draw(canvas)
            w, h = canvas.size
            # shadow + text centered
            title = "▶"
            subtitle = "Click to preview"
            main_fs = max(34, min(64, w // 8))
            sub_fs = max(18, min(30, w // 18))
            try:
                from PIL import ImageFont
                font_main = ImageFont.truetype("DejaVuSans-Bold.ttf", main_fs)
                font_sub = ImageFont.truetype("DejaVuSans-Bold.ttf", sub_fs)
            except Exception:
                font_main = None
                font_sub = None

            main_bbox = draw.textbbox((0, 0), title, font=font_main)
            sub_bbox = draw.textbbox((0, 0), subtitle, font=font_sub)
            main_w = main_bbox[2] - main_bbox[0]
            main_h = main_bbox[3] - main_bbox[1]
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_h = sub_bbox[3] - sub_bbox[1]
            total_h = main_h + 12 + sub_h
            x_main = (w - main_w) / 2
            x_sub = (w - sub_w) / 2
            y0 = (h - total_h) / 2 - 8

            shadow = (0, 0, 0, 220)
            fg = (255, 224, 130, 255) if hover else (255, 255, 255, 255)
            for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,2),(-2,2),(2,-2)]:
                draw.text((x_main+dx, y0+dy), title, font=font_main, fill=shadow)
                draw.text((x_sub+dx, y0+main_h+12+dy), subtitle, font=font_sub, fill=shadow)
            draw.text((x_main, y0), title, font=font_main, fill=fg)
            draw.text((x_sub, y0+main_h+12), subtitle, font=font_sub, fill=fg)
            return canvas.convert("RGB")
        except Exception:
            return img

    def update_preview(self, item: WallpaperItem, hover: bool = False):
        if not self.preview_enabled.get():
            self.clear_preview("Preview hidden")
            return
        if not item.supported:
            self._close_preview_popup()
            self.clear_preview("Unsupported item\nScene wallpapers are listed, but not directly playable yet.")
            return
        p = Path(item.path)
        if not p.exists():
            self.clear_preview("File not found")
            return

        self._close_preview_popup()
        self.preview_click_path = str(p) if item.media_type in {'video','html','image'} else None
        if item.media_type == 'application':
            pp = str(getattr(item, 'preview_path', '') or '')
            self.preview_click_path = pp if pp else None
        self.preview_image = None
        if item.media_type == 'video':
            self.preview_label.configure(image='', text='Loading preview…', compound='center', justify='center', font=('Segoe UI', 24, 'bold'), fg='#ffffff')
        else:
            self.preview_label.configure(image='', text='Loading preview…', compound='center', justify='center', font=('Segoe UI', 18), fg='#d7e7ff')

        self._preview_request_seq += 1
        req_id = self._preview_request_seq
        threading.Thread(target=self._render_preview_background, args=(req_id, item, hover), daemon=True).start()

    def _runtime_state_text(self) -> str:
        tray_part = "Tray active" if (self.tray_indicator is not None or self.tray_icon is not None) else "Tray inactive"
        if self.wallpaper_paused_by_fullscreen:
            return f"Status: Paused by Fullscreen • {tray_part}"
        if getattr(self.controller, "is_html_running", lambda: False)():
            return f"Status: Running HTML • {tray_part}"
        if self.controller.is_video_running() and self.controller.video_paused:
            if bool(self.store.data.get("video_mute", True)):
                return f"Status: Paused • Muted • {tray_part}"
            return f"Status: Paused • {tray_part}"
        if self.controller.is_video_running():
            if bool(self.store.data.get("video_mute", True)):
                return f"Status: Running • Muted • {tray_part}"
            return f"Status: Running • {tray_part}"
        path = self._get_last_applied_path()
        item = self._find_item_by_id(str(self.store.data.get('last_applied_id', '') or '').strip()) if path else None
        if item is not None and getattr(item, "media_type", "") == "image":
            return f"Status: Showing Image • {tray_part}"
        return f"Status: Ready • {tray_part}"

    def _now_playing_text(self) -> str:
        path = self._get_last_applied_path()
        if not path:
            return "Now Playing: Nothing active"
        item = None
        last_id = str(self.store.data.get("last_applied_id", "") or "").strip()
        if last_id:
            item = self._find_item_by_id(last_id)
        if item is None:
            for cur in self.all_items():
                if getattr(cur, "path", "") == path:
                    item = cur
                    break
        name = getattr(item, "name", "") or Path(path).stem
        if len(name) > 58:
            name = name[:55] + "..."
        media = (getattr(item, "media_type", "") or "").upper()
        suffix = f" [{media}]" if media else ""
        return f"Now Playing: {name}{suffix}"

    def _refresh_runtime_state(self):
        try:
            self.runtime_state_var.set(self._runtime_state_text())
        except Exception:
            pass
        try:
            self.now_playing_var.set(self._now_playing_text())
        except Exception:
            pass
        self._update_tray_menu()

    def set_status(self, text: str):
        self.status_var.set(text)
        self._refresh_runtime_state()

    def _playlist_pool(self) -> List[WallpaperItem]:
        enabled = [i for i in self.all_items() if i.supported and getattr(i, 'enabled', True)]
        return enabled


    def _update_pause_button(self):
        btn = getattr(self, "pause_btn", None)
        if btn is None:
            self._refresh_runtime_state()
            return
        if getattr(self.controller, "is_html_running", lambda: False)():
            try:
                btn.configure(text="Pause unavailable for HTML", state="disabled")
            except Exception:
                pass
            self._refresh_runtime_state()
            return
        if not self.controller.is_video_running():
            try:
                btn.configure(text="Pause Wallpaper", state="disabled")
            except Exception:
                pass
            self._refresh_runtime_state()
            return
        if self.wallpaper_paused_by_fullscreen:
            try:
                btn.configure(text="Paused by Fullscreen", state="disabled")
            except Exception:
                pass
            self._refresh_runtime_state()
            return
        label = "Resume Wallpaper" if self.controller.video_paused else "Pause Wallpaper"
        try:
            btn.configure(text=label, state="normal")
        except Exception:
            pass
        self._refresh_runtime_state()

    def toggle_wallpaper_pause(self):
        if self.wallpaper_paused_by_fullscreen:
            self._update_pause_button()
            self.set_status("Wallpaper is currently paused automatically because a fullscreen window is active.")
            return
        if getattr(self.controller, "is_html_running", lambda: False)():
            self.wallpaper_paused_by_user = False
            self.wallpaper_paused_by_fullscreen = False
            self._update_pause_button()
            self.set_status("Pause is currently only available for video wallpapers.")
            return
        if not self.controller.is_video_running():
            self.wallpaper_paused_by_user = False
            self.wallpaper_paused_by_fullscreen = False
            self._update_pause_button()
            self.set_status("No active video wallpaper to pause.")
            return
        if self.controller.video_paused:
            if self.controller.resume_video():
                self.wallpaper_paused_by_user = False
                self.wallpaper_paused_by_fullscreen = False
                self.set_status("Video wallpaper resumed.")
        else:
            if self.controller.pause_video():
                self.wallpaper_paused_by_user = True
                self.wallpaper_paused_by_fullscreen = False
                self.set_status("Video wallpaper paused.")
        self._update_pause_button()


    def _debug(self, message: str) -> None:
        return

    def _has_fullscreen_window_x11(self):
        if not session_is_x11() or not command_exists("xprop"):
            self._debug(f"fullscreen detect skipped session_x11={session_is_x11()} xprop={command_exists('xprop')}")
            return False

        monitors = list_monitors()
        if not monitors:
            self._debug("fullscreen detect no monitors returned")
            return False

        monitor_bounds = [
            (
                int(m.get("x", 0)),
                int(m.get("y", 0)),
                max(1, int(m.get("width", 0) or 0)),
                max(1, int(m.get("height", 0) or 0)),
            )
            for m in monitors
        ]

        def _looks_fullscreen(x: int, y: int, w: int, h: int) -> bool:
            for mx, my, mw, mh in monitor_bounds:
                right = x + w
                bottom = y + h
                if abs(x - mx) <= 20 and abs(y - my) <= 20 and w >= mw - 40 and h >= mh - 40:
                    return True
                if x <= mx + 20 and y <= my + 20 and right >= (mx + mw - 20) and bottom >= (my + mh - 20):
                    return True
                if abs(x - mx) <= 40 and right >= (mx + mw - 20) and y <= my + 120 and bottom >= (my + mh - 8):
                    return True
                if x <= mx + 40 and y <= my + 120 and right >= (mx + mw - 20) and h >= mh - 120:
                    return True
            return False

        def _window_geometry(win_id: str):
            if command_exists("xdotool"):
                try:
                    res = subprocess.run(["xdotool", "getwindowgeometry", "--shell", win_id], capture_output=True, text=True, check=False)
                    shell = res.stdout or ""
                    x_m = re.search(r"X=(-?\d+)", shell)
                    y_m = re.search(r"Y=(-?\d+)", shell)
                    w_m = re.search(r"WIDTH=(\d+)", shell)
                    h_m = re.search(r"HEIGHT=(\d+)", shell)
                    if x_m and y_m and w_m and h_m:
                        return int(x_m.group(1)), int(y_m.group(1)), int(w_m.group(1)), int(h_m.group(1))
                except Exception:
                    pass
            try:
                geo_res = subprocess.run(["xwininfo", "-id", win_id], capture_output=True, text=True, check=False)
                geo_txt = geo_res.stdout or ""
                x_m = re.search(r"Absolute upper-left X:\s+(-?\d+)", geo_txt)
                y_m = re.search(r"Absolute upper-left Y:\s+(-?\d+)", geo_txt)
                w_m = re.search(r"Width:\s+(\d+)", geo_txt)
                h_m = re.search(r"Height:\s+(\d+)", geo_txt)
                if x_m and y_m and w_m and h_m:
                    return int(x_m.group(1)), int(y_m.group(1)), int(w_m.group(1)), int(h_m.group(1))
            except Exception:
                pass
            return None

        try:
            root_res = subprocess.run(["xprop", "-root", "_NET_CURRENT_DESKTOP", "_NET_ACTIVE_WINDOW"], capture_output=True, text=True, check=False)
            root_text = ((root_res.stdout or "") + "\n" + (root_res.stderr or "")).strip()
            desk_match = re.search(r"_NET_CURRENT_DESKTOP\(CARDINAL\) = (\d+)", root_text)
            current_desktop = int(desk_match.group(1)) if desk_match else None
            active_match = re.search(r"_NET_ACTIVE_WINDOW\(WINDOW\): window id # (0x[0-9a-fA-F]+)", root_text)
            active_id = active_match.group(1).lower() if active_match else None

            root_info = subprocess.run(["xwininfo", "-root"], capture_output=True, text=True, check=False)
            root_match = re.search(r"Window id: (0x[0-9a-fA-F]+)", root_info.stdout or "")
            root_id = root_match.group(1).lower() if root_match else None

            candidates = []
            if command_exists("xdotool"):
                try:
                    xdo = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True, check=False)
                    wid_dec = (xdo.stdout or "").strip()
                    if wid_dec.isdigit():
                        wid_hex = hex(int(wid_dec)).lower()
                        if wid_hex not in {"0x0", root_id}:
                            candidates.append(wid_hex)
                except Exception as exc:
                    self._debug(f"fullscreen detect xdotool activewindow failed: {exc}")
            if active_id and active_id not in candidates and active_id not in {"0x0", root_id}:
                candidates.append(active_id)

            if command_exists("wmctrl"):
                wmctrl_res = subprocess.run(["wmctrl", "-lpGx"], capture_output=True, text=True, check=False)
                for line in (wmctrl_res.stdout or "").splitlines():
                    parts = line.split(None, 8)
                    if len(parts) < 9:
                        continue
                    wid = parts[0].lower()
                    if wid in candidates or wid in {"0x0", root_id}:
                        continue
                    candidates.append(wid)

            self._debug(f"fullscreen detect root_text={root_text!r} root_id={root_id} active_id={active_id} current_desktop={current_desktop} monitors={monitor_bounds} candidates={candidates[:8]}")
            for win_id in candidates:
                prop_res = subprocess.run(["xprop", "-id", win_id, "WM_CLASS", "_NET_WM_NAME", "_NET_WM_STATE", "_NET_WM_DESKTOP", "_NET_WM_WINDOW_TYPE", "_NET_FRAME_EXTENTS"], capture_output=True, text=True, check=False)
                props_raw = ((prop_res.stdout or "") + "\n" + (prop_res.stderr or "")).strip()
                props = props_raw.lower()
                geo = _window_geometry(win_id)
                reason = []
                if "mint-wallpaper-studio" in props or "_net_wm_window_type_desktop" in props:
                    reason.append("skip_self_or_desktop")
                if "_net_wm_state_hidden" in props:
                    reason.append("skip_hidden")
                if current_desktop is not None:
                    desk_m = re.search(r"_net_wm_desktop\(cardinal\) = (-?\d+)", props)
                    if desk_m and int(desk_m.group(1)) not in (-1, current_desktop):
                        reason.append(f"skip_desktop={desk_m.group(1)}")
                fullscreen_state = "_net_wm_state_fullscreen" in props
                geo_full = bool(geo and _looks_fullscreen(*geo))
                self._debug(f"fullscreen candidate win_id={win_id} fullscreen_state={fullscreen_state} geo={geo} geo_full={geo_full} props={props_raw!r} reasons={reason}")
                if reason:
                    continue
                if fullscreen_state or geo_full:
                    self._debug(f"fullscreen detect matched win_id={win_id} fullscreen_state={fullscreen_state} geo_full={geo_full}")
                    return True
            self._debug("fullscreen detect no match")
            return False
        except Exception as exc:
            self._debug(f"fullscreen detect exception: {exc}")
            return False

    def _start_fullscreen_monitor(self):
        try:
            if self._fullscreen_monitor_thread and self._fullscreen_monitor_thread.is_alive():
                return
        except Exception:
            pass
        self._fullscreen_monitor_stop.clear()
        self._debug(f"fullscreen monitor thread starting enabled={self.pause_on_fullscreen_enabled} session_x11={session_is_x11()}")
        self._fullscreen_monitor_thread = threading.Thread(target=self._fullscreen_monitor_loop, name="mws-fullscreen-monitor", daemon=True)
        self._fullscreen_monitor_thread.start()

    def _queue_fullscreen_ui_update(self, *, status: str | None = None, refresh_only: bool = False):
        def _apply():
            if status:
                try:
                    self.set_status(status)
                except Exception:
                    pass
            try:
                self._update_pause_button()
            except Exception:
                pass
        try:
            self.root.after(0, _apply)
        except Exception:
            pass

    def _fullscreen_monitor_loop(self):
        self._debug("fullscreen monitor loop entered")
        tick_no = 0
        while not self._fullscreen_monitor_stop.is_set() and not getattr(self, "_shutdown", False):
            try:
                tick_no += 1
                active_video = self.controller.is_video_running()
                auto_pause_enabled = bool(getattr(self, "pause_on_fullscreen_enabled", True))
                fullscreen_active = active_video and auto_pause_enabled and self._has_fullscreen_window_x11()
                state = (bool(active_video), bool(auto_pause_enabled), bool(fullscreen_active), bool(self.controller.video_paused), bool(self.wallpaper_paused_by_fullscreen))
                if tick_no <= 5 or tick_no % 10 == 0:
                    self._debug(f"fullscreen loop heartbeat tick={tick_no} active_video={active_video} auto_pause_enabled={auto_pause_enabled} fullscreen_active={fullscreen_active} video_paused={self.controller.video_paused} paused_by_fullscreen={self.wallpaper_paused_by_fullscreen}")
                if state != self._last_fullscreen_debug_state:
                    self._last_fullscreen_debug_state = state
                    self._debug(f"fullscreen tick active_video={active_video} auto_pause_enabled={auto_pause_enabled} fullscreen_active={fullscreen_active} video_paused={self.controller.video_paused} paused_by_fullscreen={self.wallpaper_paused_by_fullscreen}")

                if fullscreen_active and not self.controller.video_paused:
                    paused = self.controller.pause_video()
                    self._debug(f"fullscreen pause attempt result={paused}")
                    if paused:
                        self.wallpaper_paused_by_fullscreen = True
                        self.wallpaper_paused_by_user = False
                        self._queue_fullscreen_ui_update(status="Paused video wallpaper because a fullscreen window is active.")
                elif (
                    active_video
                    and self.controller.video_paused
                    and self.wallpaper_paused_by_fullscreen
                    and not fullscreen_active
                ):
                    resumed = self.controller.resume_video()
                    self._debug(f"fullscreen resume attempt result={resumed}")
                    if resumed:
                        self.wallpaper_paused_by_fullscreen = False
                        self._queue_fullscreen_ui_update(status="Resumed video wallpaper after fullscreen window closed.")
                elif not active_video:
                    if self.wallpaper_paused_by_fullscreen or self.wallpaper_paused_by_user:
                        self._debug("fullscreen tick clearing paused flags because no active video")
                    self.wallpaper_paused_by_fullscreen = False
                    self.wallpaper_paused_by_user = False
                    self._queue_fullscreen_ui_update(refresh_only=True)
            except Exception as exc:
                self._debug(f"fullscreen tick exception: {exc}")
            self._fullscreen_monitor_stop.wait(1.0)

    def _fullscreen_pause_tick(self):
        # Legacy path retained for compatibility; dedicated background thread handles fullscreen pause/resume.
        self._start_fullscreen_monitor()

    def _apply_item_async(self, item: WallpaperItem, save_mode: str = "single"):
        if getattr(self, "_apply_in_progress", False):
            self.set_status("Please wait for the current wallpaper launch to finish.")
            return
        self._apply_in_progress = True
        self.set_status(f"Starting {item.name}...")

        def worker():
            result = {"ok": False, "method": None, "error": None}
            try:
                result["method"] = self.controller.apply(item)
                result["ok"] = True
            except Exception as exc:
                result["error"] = str(exc)

            def done():
                self._apply_in_progress = False
                if result["ok"]:
                    try:
                        self._save_last_applied(item, save_mode)
                    except Exception:
                        pass
                    self.set_status(f"Applied: {item.name} via {result['method']}")
                    self.refresh_list()
                    self._refresh_runtime_state()
                else:
                    self.set_status(f"Error: {result['error']}")
                    self._show_error(APP_NAME, result['error'])
            try:
                self.root.after(0, done)
            except Exception:
                done()

        threading.Thread(target=worker, daemon=True).start()

    def apply_selected(self):
        item = self.primary_item()
        if not item:
            self.set_status("No item selected")
            return
        if not item.supported:
            self._show_info(APP_NAME, "This item is preview-only right now. Scene wallpapers are listed, but not directly playable yet.")
            return
        try:
            if item.media_type == "application":
                self._apply_item_async(item, "single")
                return
            status = self._apply_item_for_current_monitor_context(item, "Applied")
            self.set_status(status)
            self.refresh_list()
            self._refresh_runtime_state()
        except Exception as exc:
            self.set_status(f"Error: {exc}")
            self._show_error(APP_NAME, str(exc))

    def select_random(self):
        pool = self._playlist_pool() or [i for i in self.filtered if i.supported]
        if not pool:
            return
        item = random.choice(pool)
        self._select_item_in_current_view(item)

    def _select_item_in_current_view(self, item: WallpaperItem):
        self.refresh_list()
        for idx, cur in enumerate(self.filtered):
            if cur.path == item.path:
                iid = str(idx)
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
                self.on_select()
                return
        self.on_select()

    def apply_random(self):
        if self.monitor_mode.get() == "per_monitor" and self._auto_scope_effective() in {"workspace", "monitors"}:
            layout = self._build_random_monitor_layout()
            if not layout:
                self.set_status("No supported image/video playlist items available for the current monitors")
                return
            try:
                status = self._apply_items_to_monitor_layout(layout, "Random wallpaper applied")
                self._save_last_multi_layout(layout)
                for item in layout.values():
                    self._remember_random_pick(item)
                self.set_status(status)
                self.refresh_list()
                self._refresh_runtime_state()
            except Exception as exc:
                self.set_status(f"Error: {exc}")
            return

        if self.monitor_mode.get() != "per_monitor" or len(self._monitor_names()) <= 1 or self._auto_scope_effective() != "target":
            pool = self._playlist_pool() or [i for i in self.filtered if i.supported]
            if not pool:
                self.set_status("No supported playlist items available")
                return
            item = self._pick_less_repetitive_random(pool)
            if not item:
                self.set_status("No supported playlist items available")
                return
            self._select_item_in_current_view(item)
            try:
                status = self._apply_item_for_current_monitor_context(item, "Random wallpaper applied")
                self._remember_random_pick(item)
                self.set_status(status)
                self.refresh_list()
                self._refresh_runtime_state()
            except Exception as exc:
                self.set_status(f"Error: {exc}")
            return

        target = self.playlist_target.get() or "synced"
        pool = self._playlist_pool_for_target(target, supported_only=True)
        if not pool:
            self.set_status(f"No supported playlist items available for {target}")
            return
        item = self._pick_less_repetitive_random(pool)
        if not item:
            self.set_status(f"No supported playlist items available for {target}")
            return
        self._select_item_in_current_view(item)
        try:
            status = self._apply_item_for_current_monitor_context(item, "Random wallpaper applied")
            self._remember_random_pick(item)
            self.set_status(status)
            self.refresh_list()
            self._refresh_runtime_state()
        except Exception as exc:
            self.set_status(f"Error: {exc}")

    def toggle_selected_playlist(self):
        sel = self.selected_items()
        if not sel:
            return
        target = not all(i.enabled for i in sel)
        for item in sel:
            self._set_item_enabled_for_target(item, target)
        self._persist_items()
        self.refresh_list()
        self.set_status(f"{'Enabled' if target else 'Disabled'} {len(sel)} item(s) for the playlist")

    def enable_selected(self):
        self._set_selected_enabled(True)

    def disable_selected(self):
        self._set_selected_enabled(False)

    def _set_selected_enabled(self, value: bool):
        sel = self.selected_items()
        if not sel:
            return
        for item in sel:
            self._set_item_enabled_for_target(item, value)
        self._persist_items()
        self.refresh_list()
        self.set_status(f"{'Enabled' if value else 'Disabled'} {len(sel)} item(s) for the playlist")

    def _on_tree_click(self, event):
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if iid and col == '#1':
            try:
                item = self.filtered[int(iid)]
            except Exception:
                return
            self._set_item_enabled_for_target(item, not self._item_enabled_for_target(item))
            self._persist_items()
            self.refresh_list()
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            self.on_select()

    def _on_double_click(self, event):
        col = self.tree.identify_column(event.x)
        if col != "#1":
            self.apply_selected()

    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.tree.focus(row)
            self.on_select()
        self._refresh_context_menu()
        self._update_pause_button()
        self._show_context_menu(event.x_root, event.y_root)
        return "break"

    def _on_context_key(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return "break"
        row = sel[0]
        bbox = self.tree.bbox(row, "#1")
        if bbox:
            x = self.tree.winfo_rootx() + bbox[0] + 20
            y = self.tree.winfo_rooty() + bbox[1] + 20
        else:
            x = self.tree.winfo_rootx() + 30
            y = self.tree.winfo_rooty() + 30
        self._show_context_menu(x, y)
        return "break"

    def rename_selected(self):
        item = self.primary_item()
        if not item:
            return
        new_name = simple_input(self.root, "Rename Item", "New name:", item.name)
        if not new_name:
            return
        item.name = new_name.strip()
        self._persist_items()
        self.refresh_list()
        self.set_status(f"Renamed: {item.name}")

    def _refresh_context_menu(self):
        sel = self.selected_items()
        count = len(sel)
        try:
            self.context_menu.delete(0, "end")
        except Exception:
            return

        self.context_menu.add_command(label="Apply", command=self.apply_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Pick / Enable", command=self.enable_selected)
        self.context_menu.add_command(label="Unpick / Disable", command=self.disable_selected)
        self.context_menu.add_separator()

        if count <= 1:
            if self.tab_var.get() == "all":
                self.context_menu.add_command(label="Move to Top", command=self._move_selected_top)
                self.context_menu.add_command(label="Move Up", command=lambda: self._move_selected_relative(-1))
                self.context_menu.add_command(label="Move Down", command=lambda: self._move_selected_relative(1))
                self.context_menu.add_command(label="Move to Bottom", command=self._move_selected_bottom)
                self.context_menu.add_separator()
            else:
                self.context_menu.add_command(label="Move only in All playlist", state="disabled")
                self.context_menu.add_separator()
            self.context_menu.add_command(label="Rename", command=self.rename_selected)
            self.context_menu.add_command(label="Open Folder", command=self.open_selected_folder)
        else:
            self.context_menu.add_command(label=f"{count} items selected", state="disabled")
            self.context_menu.add_separator()
            self.context_menu.add_command(label="Open Folder", command=self.open_selected_folder)
        self.context_menu.add_command(label="Delete", command=self.remove_selected)

    def _close_context_menu(self, event=None):
        try:
            if hasattr(self, "context_menu"):
                self.context_menu.unpost()
        except Exception:
            pass
        try:
            self.root.unbind_all("<Escape>")
        except Exception:
            pass

    def _run_context_action(self, callback):
        try:
            callback()
        finally:
            try:
                self._close_context_menu()
            except Exception:
                pass

    def _show_context_menu(self, x_root: int, y_root: int):
        try:
            self.context_menu.tk_popup(x_root, y_root)
            try:
                self.context_menu.bind("<Unmap>", self._close_context_menu, add="+")
            except Exception:
                pass
            self.root.bind_all("<Escape>", self._close_context_menu, add="+")
        finally:
            try:
                self.context_menu.grab_release()
            except Exception:
                pass

    def _auto_change_is_paused(self) -> bool:
        return bool(getattr(self, "wallpaper_paused_by_user", False) or getattr(self, "wallpaper_paused_by_fullscreen", False))

    def _has_active_per_monitor_auto_change_rows(self) -> bool:
        per = dict(self.store.data.get("auto_change_per_monitor", {}) or {})
        for mon in self._monitor_names():
            row = dict(per.get(mon, {}) or {})
            mode = str(row.get("mode", "off") or "off")
            if mode != "off":
                return True
        return False

    def _per_monitor_auto_change_requested(self) -> bool:
        if self._monitor_mode_effective() != "per_monitor":
            return False
        enabled = bool(self.store.data.get("auto_change_per_monitor_enabled", False))
        preference = bool(self.store.data.get("auto_change_per_monitor_preference", False))
        has_rows = self._has_active_per_monitor_auto_change_rows()
        requested = enabled or (preference and has_rows) or has_rows
        if requested and not enabled:
            self._debug(
                f"autochange per-monitor fallback engaged enabled={enabled} preference={preference} has_rows={has_rows}"
            )
        return requested

    def _current_auto_targets(self) -> list[tuple[str, str, int]]:
        targets: list[tuple[str, str, int]] = []
        try:
            base_interval = max(1, int(self.auto_interval_var.get()))
        except Exception:
            base_interval = 10
            try:
                self.auto_interval_var.set(base_interval)
            except Exception:
                pass

        if self._per_monitor_auto_change_requested():
            per = dict(self.store.data.get("auto_change_per_monitor", {}) or {})
            for mon in self._monitor_names():
                row = dict(per.get(mon, {}) or {})
                mode = str(row.get("mode", "off") or "off")
                if mode == "off":
                    continue
                try:
                    interval = max(1, int(row.get("interval", base_interval)))
                except Exception:
                    interval = base_interval
                targets.append((f"monitor:{mon}", mode, interval))
            if targets:
                return targets
            self._debug("autochange per-monitor requested but no active monitor rows found; shared fallback suppressed")
            return []

        mode = self.auto_mode_var.get()
        if self._monitor_mode_effective() == "per_monitor" and self._has_active_per_monitor_auto_change_rows():
            self._debug(
                f"autochange shared fallback blocked mode={mode!r} enabled={self.store.data.get('auto_change_per_monitor_enabled', False)!r} "
                f"preference={self.store.data.get('auto_change_per_monitor_preference', False)!r}"
            )
            return []
        if mode != "off":
            targets.append(("shared", mode, base_interval))
        return targets

    def _reset_auto_scheduler(self, preserve_elapsed: bool = False) -> None:
        now = time.monotonic()
        self._last_auto_scheduler_ts = now
        current = self._current_auto_targets()
        current_ids = {target_id for target_id, _mode, _interval in current}
        deadlines = dict(getattr(self, "_auto_next_deadline", {}) or {})
        deadlines = {k: v for k, v in deadlines.items() if k in current_ids}
        if not preserve_elapsed:
            deadlines = {}
        for target_id, _mode, interval in current:
            if target_id not in deadlines:
                deadlines[target_id] = now + float(interval * 60)
        self._auto_next_deadline = deadlines

    def _run_auto_change_target(self, target_id: str, mode: str) -> None:
        self._debug(f"autochange target start id={target_id!r} mode={mode!r} effective_mode={self._monitor_mode_effective()!r} current_images={self._get_current_image_monitor_layout()!r} current_videos={self._get_current_video_monitor_layout()!r}")
        if target_id == "shared":
            if mode == "random":
                self.apply_random()
            elif mode == "playlist":
                self.apply_next_playlist()
            self._debug(f"autochange target done id={target_id!r} mode={mode!r} current_images={self._get_current_image_monitor_layout()!r} current_videos={self._get_current_video_monitor_layout()!r}")
            return

        if not target_id.startswith("monitor:"):
            self._debug(f"autochange target ignored id={target_id!r}")
            return
        monitor = target_id.split(":", 1)[1]
        previous_target = self.playlist_target.get()
        applied_item = None
        try:
            self.playlist_target.set(monitor)
            if mode == "random":
                pool = self._playlist_pool_for_target(monitor, supported_only=True)
                self._debug(f"autochange target pool monitor={monitor!r} size={len(pool)} mode='random'")
                if not pool:
                    return
                item = self._pick_less_repetitive_random(pool)
                if not item:
                    return
                self._remember_random_pick(item)
                self._debug(f"autochange target picked monitor={monitor!r} item={getattr(item, 'path', '')!r} media={getattr(item, 'media_type', '')!r}")
                self._apply_item_for_current_monitor_context(item, f"Random wallpaper applied to {monitor}")
                applied_item = item
            elif mode == "playlist":
                pool = self._playlist_pool_for_target(monitor, supported_only=True)
                self._debug(f"autochange target pool monitor={monitor!r} size={len(pool)} mode='playlist'")
                if not pool:
                    return
                last_layout = dict(self.store.data.get("last_monitor_layout", {}) or {})
                last_path = str(last_layout.get(monitor, "") or "")
                idx = -1
                for n, item in enumerate(pool):
                    if item.path == last_path:
                        idx = n
                        break
                item = pool[(idx + 1) % len(pool)]
                self._debug(f"autochange target picked monitor={monitor!r} item={getattr(item, 'path', '')!r} media={getattr(item, 'media_type', '')!r} last_path={last_path!r}")
                self._apply_item_for_current_monitor_context(item, f"Playlist wallpaper applied to {monitor}")
                applied_item = item
        finally:
            if applied_item is not None:
                try:
                    last_layout = dict(self.store.data.get("last_monitor_layout", {}) or {})
                    last_layout[monitor] = str(getattr(applied_item, "path", "") or "")
                    self.store.data["last_monitor_layout"] = last_layout
                except Exception:
                    pass
            try:
                self.playlist_target.set(previous_target)
            except Exception:
                pass
            self._debug(f"autochange target end id={target_id!r} mode={mode!r} restored_target={previous_target!r} current_images={self._get_current_image_monitor_layout()!r} current_videos={self._get_current_video_monitor_layout()!r}")

    def _schedule_next_auto_tick(self) -> None:
        try:
            if self.random_job:
                self.root.after_cancel(self.random_job)
        except Exception:
            pass
        self.random_job = None
        active_targets = self._current_auto_targets()
        if active_targets:
            self.random_job = self.root.after(int(getattr(self, "_auto_tick_ms", 1000)), self._tick_auto_change)

    def _tick_auto_change(self):
        self.random_job = None
        self._blink_on = True
        self._blink_job = None
        self._auto_scheduler_step()
        self._schedule_next_auto_tick()

    def _auto_scheduler_step(self) -> None:
        current = self._current_auto_targets()
        current_ids = {target_id for target_id, _mode, _interval in current}
        if current_ids != set(getattr(self, "_auto_next_deadline", {}).keys()):
            self._maybe_restart_auto_scheduler(force=False)
            current = self._current_auto_targets()
            current_ids = {target_id for target_id, _mode, _interval in current}
        now = time.monotonic()
        self._last_auto_scheduler_ts = now
        if self._auto_change_is_paused():
            self._debug(f"autochange paused current={current!r}")
            return
        deadlines = dict(getattr(self, "_auto_next_deadline", {}) or {})
        deadlines = {k: v for k, v in deadlines.items() if k in current_ids}
        self._debug(f"autochange scheduler step current={current!r} deadlines_before={deadlines!r}")
        for target_id, mode, interval in current:
            period = float(interval * 60)
            next_deadline = float(deadlines.get(target_id, now + period))
            if now >= next_deadline:
                self._debug(f"autochange due id={target_id!r} mode={mode!r} interval={interval} now={now:.3f} next_deadline={next_deadline:.3f}")
                self._run_auto_change_target(target_id, mode)
                while next_deadline <= now:
                    next_deadline += period
            deadlines[target_id] = next_deadline
        self._auto_next_deadline = deadlines
        self._debug(f"autochange scheduler step done deadlines_after={deadlines!r}")

    def _auto_scheduler_signature(self) -> tuple:
        targets = tuple((target_id, mode, int(interval)) for target_id, mode, interval in self._current_auto_targets())
        return (str(self._monitor_mode_effective() or "shared"), targets)

    def _maybe_restart_auto_scheduler(self, *, force: bool = False) -> None:
        new_sig = self._auto_scheduler_signature()
        old_sig = getattr(self, "_auto_scheduler_signature_cache", None)
        if force or old_sig != new_sig:
            self._auto_scheduler_signature_cache = new_sig
            self._reset_auto_scheduler(preserve_elapsed=False)
        else:
            self._auto_scheduler_signature_cache = new_sig

    def _apply_auto_scheduler_changes(self, old_signature: tuple, new_signature: tuple) -> None:
        try:
            old_mode, old_auto_mode, old_interval, old_per_enabled, _old_pref, old_per_repr = old_signature
            new_mode, new_auto_mode, new_interval, new_per_enabled, _new_pref, new_per_repr = new_signature
        except Exception:
            self._maybe_restart_auto_scheduler(force=True)
            return

        def _safe_eval_dict(raw: str) -> dict:
            try:
                import ast
                value = ast.literal_eval(raw)
                return dict(value or {}) if isinstance(value, dict) else {}
            except Exception:
                return {}

        current = self._current_auto_targets()
        if not current:
            self._maybe_restart_auto_scheduler(force=True)
            self._schedule_next_auto_tick()
            return

        old_per = _safe_eval_dict(old_per_repr)
        new_per = _safe_eval_dict(new_per_repr)
        deadlines = dict(getattr(self, "_auto_next_deadline", {}) or {})
        changed_targets = set()

        if old_mode != new_mode or old_per_enabled != new_per_enabled or old_auto_mode != new_auto_mode:
            changed_targets = {target_id for target_id, _mode, _interval in current}
        elif new_mode == "per_monitor" and new_per_enabled:
            for target_id, mode, interval in current:
                mon = target_id.split(":", 1)[1] if target_id.startswith("monitor:") else None
                old_row = dict(old_per.get(mon, {}) or {})
                new_row = dict(new_per.get(mon, {}) or {})
                if str(old_row.get("mode", "off")) != str(new_row.get("mode", "off")) or int(old_row.get("interval", interval) or interval) != int(new_row.get("interval", interval) or interval):
                    changed_targets.add(target_id)
        elif old_interval != new_interval:
            changed_targets = {"shared"}

        self._auto_scheduler_signature_cache = self._auto_scheduler_signature()
        now = time.monotonic()
        self._last_auto_scheduler_ts = now
        valid_ids = {target_id for target_id, _mode, _interval in current}
        deadlines = {k: v for k, v in deadlines.items() if k in valid_ids}
        for target_id, _mode, interval in current:
            if target_id in changed_targets or target_id not in deadlines:
                deadlines[target_id] = now + float(interval * 60)
        self._auto_next_deadline = deadlines
        self._schedule_next_auto_tick()

    def _start_random_if_enabled(self):
        if self.random_job:
            self.root.after_cancel(self.random_job)
            self.random_job = None
        self._blink_on = True
        self._blink_job = None
        mode = self.auto_mode_var.get()
        self.store.data["auto_change_mode"] = mode
        per_enabled = self._per_monitor_auto_change_requested()
        self.store.data["random_enabled"] = (mode != "off") or per_enabled
        try:
            mins = max(1, int(self.auto_interval_var.get()))
        except Exception:
            mins = 10
            self.auto_interval_var.set(mins)
        self.store.data["random_interval_minutes"] = mins
        self.store.data["auto_change_scope"] = self.auto_change_scope_var.get()
        self._reset_auto_scheduler(preserve_elapsed=False)
        self.store.save()
        self._schedule_next_auto_tick()

    def _auto_controls_changed(self):
        self._update_auto_change_hint()
        self._start_random_if_enabled()
        mode = self.auto_mode_var.get()
        try:
            mins = int(self.auto_interval_var.get())
        except Exception:
            mins = 10
        scope = self._auto_scope_effective()
        if mode == "off":
            self.set_status("Auto change disabled")
        elif mode == "playlist":
            detail = "selected display" if scope == "target" else ("chosen displays" if scope == "monitors" else "current desktop layout")
            self.set_status(f"Auto change uses playlist order every {mins} min for the {detail}.")
        else:
            detail = "selected display" if scope == "target" else ("chosen displays" if scope == "monitors" else "current desktop layout")
            self.set_status(f"Auto change uses random mode every {mins} min for the {detail}.")

    def _get_last_applied_path(self) -> str:
        return str(self.store.data.get("last_applied_path", "") or "")

    def _playlist_enabled_supported(self) -> list[WallpaperItem]:
        return [i for i in self.all_items() if getattr(i, "enabled", True) and getattr(i, "supported", True)]

    def _build_playlist_monitor_layout_for_targets(self, targets: list[str]) -> dict[str, WallpaperItem]:
        layout: dict[str, WallpaperItem] = {}
        all_media: list[str] = []
        recent_multi = dict(self.store.data.get("last_applied_multi", {}) or {})
        for monitor in targets:
            pool = [i for i in self._playlist_pool_for_target(monitor, supported_only=True) if i.media_type in {"image", "video"}]
            if not pool:
                continue
            last_path = str(recent_multi.get(monitor, self._get_last_applied_path()) or "")
            idx = -1
            for n, cur in enumerate(pool):
                if cur.path == last_path:
                    idx = n
                    break
            item = pool[(idx + 1) % len(pool)]
            layout[monitor] = item
            all_media.append(item.media_type)
        return layout

    def _build_random_monitor_layout_for_targets(self, targets: list[str]) -> dict[str, WallpaperItem]:
        layout: dict[str, WallpaperItem] = {}
        all_media: list[str] = []
        for monitor in targets:
            pool = [i for i in self._playlist_pool_for_target(monitor, supported_only=True) if i.media_type in {"image", "video"}]
            if not pool:
                continue
            item = self._pick_less_repetitive_random(pool)
            if not item:
                continue
            layout[monitor] = item
            all_media.append(item.media_type)
        return layout

    def _per_monitor_auto_targets(self, mode_name: str) -> list[str]:
        if not self._per_monitor_auto_change_requested():
            scope = self._auto_scope_effective()
            if scope == "monitors":
                return self._auto_change_monitor_names()
            if scope == "target":
                tgt = self.playlist_target.get() or "synced"
                return [tgt] if tgt not in {"", "synced"} else []
            return self._monitor_names()
        out = []
        data = dict(self.store.data.get("auto_change_per_monitor", {}) or {})
        for mon in self._monitor_names():
            row = data.get(mon, {}) or {}
            if bool(row.get("enabled")) and str(row.get("mode", "off")) == mode_name:
                out.append(mon)
        return out

    def apply_next_playlist(self):
        if self.monitor_mode.get() == "per_monitor" and (self._auto_scope_effective() != "target" or bool(self.store.data.get("auto_change_per_monitor_enabled", False))):
            layout = self._build_playlist_monitor_layout_for_targets(self._per_monitor_auto_targets("playlist"))
            if not layout:
                self.set_status("No supported image/video playlist items available for the current monitors")
                return
            try:
                status = self._apply_items_to_monitor_layout(layout, "Playlist wallpaper applied")
                self._save_last_multi_layout(layout)
                self.set_status(status)
                self.refresh_list()
                self._refresh_runtime_state()
            except Exception as exc:
                self.set_status(f"Error: {exc}")
            return
        if self.monitor_mode.get() == "per_monitor" and self._auto_scope_effective() == "target":
            target = self.playlist_target.get() or "synced"
            pool = self._playlist_pool_for_target(target, supported_only=True)
        else:
            pool = self._playlist_enabled_supported() or [i for i in self.filtered if i.supported]
        if not pool:
            self.set_status("No supported playlist items available")
            return
        last_path = self._get_last_applied_path()
        idx = -1
        for n, item in enumerate(pool):
            if item.path == last_path:
                idx = n
                break
        item = pool[(idx + 1) % len(pool)]
        self._select_item_in_current_view(item)
        try:
            status = self._apply_item_for_current_monitor_context(item, "Playlist wallpaper applied")
            self.set_status(status)
            self.refresh_list()
            self._refresh_runtime_state()
        except Exception as exc:
            self.set_status(f"Error: {exc}")


    def advance_now(self):
        mode = self.auto_mode_var.get()
        if mode == "playlist":
            self.apply_next_playlist()
        elif mode == "random":
            self.apply_random()
        else:
            self.apply_selected()

    def open_add_window(self):
        win = tk.Toplevel(self.root)
        self._style_toplevel(win, title="Add Media", geometry="1120x760")
        win.minsize(980, 680)
        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Add Media", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Choose files or folders. Supported images, videos, HTML wallpapers, and Windows .exe application wallpapers will be imported into the local library.", style="Sub.TLabel").pack(anchor="w", pady=(0, 12))

        actions = ttk.Frame(outer, style="Card.TFrame")
        actions.pack(fill="x")
        left_actions = ttk.Frame(actions, style="Card.TFrame")
        left_actions.pack(side="left")

        selected: List[Path] = []

        drop_hint = tk.StringVar(value="Drag files or folders here, or use Add Files / Add Folder.")
        drop = tk.Label(
            outer,
            textvariable=drop_hint,
            bg="#0a1020",
            fg="#d7e7ff",
            font=("Segoe UI", 12, "bold"),
            relief="ridge",
            bd=2,
            padx=12,
            pady=16,
        )
        drop.pack(fill="x", pady=(0, 10))

        list_wrap = ttk.Frame(outer, style="Alt.TFrame")
        list_wrap.pack(fill="both", expand=True, pady=10)
        tree = ttk.Treeview(list_wrap, columns=("kind", "path"), show="headings", selectmode="extended")
        tree.pack(fill="both", expand=True)
        tree.heading("kind", text="Kind")
        tree.heading("path", text="Path")
        tree.column("kind", width=140, anchor="center")
        tree.column("path", width=900, anchor="w")
        empty_hint = tk.Label(
            list_wrap,
            text="Drop a file or folder anywhere in this window, or use Add Files / Add Folder.",
            bg="#10203a",
            fg="#d7e7ff",
            font=("Segoe UI", 12, "bold"),
            pady=14,
        )
        empty_hint.place(relx=0.5, rely=0.5, anchor="center")

        def add_path(p: Path):
            if not p.exists():
                return
            if p not in selected:
                selected.append(p)

        def redraw():
            tree.delete(*tree.get_children())
            for idx, p in enumerate(selected):
                kind = "Folder" if p.is_dir() else (classify_media(p) or "Unknown").title()
                tree.insert("", "end", iid=str(idx), values=(kind, str(p)))
            if selected:
                empty_hint.place_forget()
            else:
                empty_hint.place(relx=0.5, rely=0.5, anchor="center")

        def add_files():
            files = filedialog.askopenfilenames(parent=win, title="Select media files", filetypes=[("Supported media", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.webm *.mkv *.mov *.avi *.html *.htm *.exe"), ("All files", "*.*")])
            for f in files:
                p = Path(f)
                if p.exists() and classify_media(p):
                    add_path(p)
            redraw()

        def add_folder():
            folder = filedialog.askdirectory(parent=win, title="Select folder")
            if folder:
                add_path(Path(folder))
                redraw()

        def remove_sel():
            for iid in sorted(tree.selection(), key=lambda x: int(x), reverse=True):
                selected.pop(int(iid))
            redraw()

        def parse_drop_data(data: str):
            try:
                parts = win.tk.splitlist(data)
            except Exception:
                parts = data.split()
            out = []
            for item in parts:
                item = item.strip()
                if item.startswith("{") and item.endswith("}"):
                    item = item[1:-1]
                if item:
                    out.append(Path(item))
            return out

        def on_drop(event=None):
            data = getattr(event, "data", "") if event is not None else ""
            added = 0
            for p in parse_drop_data(data):
                if p.exists():
                    add_path(p)
                    added += 1
            redraw()
            drop_hint.set(f"Added {added} dropped item(s)." if added else "Nothing usable was dropped.")

        if TkinterDnD is not None and DND_FILES is not None:
            try:
                for widget in (win, outer, drop, tree, list_wrap, empty_hint):
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind("<<Drop>>", on_drop)
                drop_hint.set("Drag files or folders anywhere in this window, or use Add Files / Add Folder.")
            except Exception:
                drop_hint.set("Drag & drop is unavailable in this environment. Use Add Files / Add Folder.")
        else:
            drop_hint.set("Drag & drop needs tkinterdnd2. Use Add Files / Add Folder for now.")

        def do_import():
            paths = scan_paths(selected)
            imported = 0
            copy_files = bool(self.store.data.get("copy_into_library"))
            for p in paths:
                media_type = classify_media(p)
                if not media_type:
                    continue
                final = p
                if copy_files:
                    INTERNAL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
                    dest = INTERNAL_LIBRARY_DIR / p.name
                    base = dest.stem
                    ext = dest.suffix
                    n = 1
                    while dest.exists():
                        dest = INTERNAL_LIBRARY_DIR / f"{base}_{n}{ext}"
                        n += 1
                    shutil.copy2(p, dest)
                    final = dest
                item = WallpaperItem.from_path(final, media_type, source="local")
                if media_type in {"application", "html"}:
                    item.enabled = False
                if not any(Path(i.path) == Path(item.path) for i in self.items):
                    self.items.append(item)
                    imported += 1
            self._persist_items()
            self.refresh_list()
            self.set_status(f"Imported {imported} item(s)")
            self.options_window = None
            win.destroy()

        for btn_text, cmd in [("Add Files", add_files), ("Add Folder", add_folder), ("Remove Selected", remove_sel)]:
            ttk.Button(left_actions, text=btn_text, command=cmd).pack(side="left", padx=(0, 6))

        bottom_bar = ttk.Frame(outer, style="Card.TFrame")
        bottom_bar.pack(fill="x", pady=(10, 0), side="bottom")
        ttk.Button(bottom_bar, text="Import", command=do_import, style="Accent.TButton", width=18).pack(side="right")

    def _application_runtime_summary(self) -> str:
        try:
            info = self.controller.get_application_runtime_info()
        except Exception as exc:
            return f"Application runtime status unavailable: {exc}"
        return self._application_runtime_summary_from_info(info)

    def _application_runtime_summary_from_info(self, info: dict) -> str:
        wine_label = info.get("wine_version") or (Path(info.get("wine_bin") or "").name if info.get("wine_bin") else "not found")
        wine_mode = info.get("wine_preferred", "standard")
        lines = [
            f"Runtime initialized: {'Yes' if info.get('runtime_initialized') else 'No'}",
            f"Wine: {wine_label} ({wine_mode})",
            f"Winetricks: {Path(info.get('winetricks_bin') or '').name if info.get('winetricks_bin') else 'not found'}",
            f"DXVK: {info.get('dxvk_status', 'unknown')}",
            f"Corefonts: {info.get('corefonts_status', 'unknown')}",
            f"Mono: {info.get('mono_status', 'unknown')}",
            f"Gecko: {info.get('gecko_status', 'unknown')}",
        ]
        return "\n".join(lines)

    def _run_application_runtime_task(self, action: str, text_var: tk.StringVar, status_msg: str = ""):
        if getattr(self, '_app_runtime_busy', False):
            self.set_status('Application runtime task is already running.')
            return
        self._app_runtime_busy = True
        text_var.set('Application runtime task running...')
        self.set_status(status_msg or 'Preparing application runtime...')

        def worker():
            try:
                if action == 'init':
                    self.controller.initialize_application_runtime(force_reset=False)
                    msg = 'Managed application runtime initialized.'
                elif action == 'reset':
                    self.controller.reset_application_runtime()
                    msg = 'Managed application runtime reset. It will be re-created on the next app start.'
                else:
                    msg = f'Unknown runtime action: {action}'
                err = None
            except Exception as exc:
                msg = None
                err = str(exc)

            def finish():
                self._app_runtime_busy = False
                refresh = getattr(self, '_refresh_application_runtime_panel', None)
                if callable(refresh):
                    refresh()
                else:
                    text_var.set(self._application_runtime_summary())
                if err:
                    self.set_status(f'Application runtime failed: {err}')
                    try:
                        self._show_error('Application Runtime', err)
                    except Exception:
                        pass
                else:
                    self.set_status(msg or 'Application runtime task finished.')
            try:
                self.root.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=worker, name='mws-app-runtime', daemon=True).start()

    def _get_application_runtime_info(self) -> dict:
        try:
            return self.controller.get_application_runtime_info()
        except Exception as exc:
            try:
                self._show_error('Application Runtime', str(exc))
            except Exception:
                pass
            return {}

    def _copy_application_prefix_path(self):
        info = self._get_application_runtime_info()
        prefix = str(info.get('prefix_dir') or '').strip()
        if not prefix:
            self.set_status('Application prefix path unavailable.')
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(prefix)
            self.root.update_idletasks()
            self.set_status('Application prefix path copied to clipboard.')
        except Exception as exc:
            self.set_status(f'Could not copy prefix path: {exc}')

    def _open_application_prefix_folder(self):
        info = self._get_application_runtime_info()
        prefix = Path(str(info.get('prefix_dir') or '').strip())
        if not str(prefix):
            self.set_status('Application prefix path unavailable.')
            return
        prefix.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(['xdg-open', str(prefix)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.set_status('Opened application prefix folder.')
        except Exception as exc:
            self.set_status(f'Could not open prefix folder: {exc}')

    def _open_application_prefix_terminal(self):
        info = self._get_application_runtime_info()
        prefix = Path(str(info.get('prefix_dir') or '').strip())
        if not str(prefix):
            self.set_status('Application prefix path unavailable.')
            return
        prefix.mkdir(parents=True, exist_ok=True)
        shell_cmd = f'cd {shlex.quote(str(prefix))}; exec bash'
        candidates = [
            ['x-terminal-emulator', f'--working-directory={prefix}'],
            ['gnome-terminal', f'--working-directory={prefix}'],
            ['xfce4-terminal', f'--working-directory={prefix}'],
            ['tilix', f'--working-directory={prefix}'],
            ['konsole', '--workdir', str(prefix)],
            ['xterm', '-e', 'bash', '-lc', shell_cmd],
        ]
        for cmd in candidates:
            if not shutil.which(cmd[0]):
                continue
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.set_status('Opened terminal in application prefix folder.')
                return
            except Exception:
                continue
        self.set_status('No supported terminal launcher was found.')

    def _launch_application_runtime_tool(self, tool: str, text_var: Optional[tk.StringVar] = None):
        info = self._get_application_runtime_info()
        prefix = Path(str(info.get('prefix_dir') or '').strip())
        if not str(prefix):
            self.set_status('Application prefix path unavailable.')
            return
        prefix.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env['WINEPREFIX'] = str(prefix)
        env.setdefault('WINEDEBUG', '-all')
        env.setdefault('WINEDLLOVERRIDES', 'winemenubuilder.exe=d')
        if tool == 'winetricks':
            bin_path = str(info.get('winetricks_bin') or '').strip() or shutil.which('winetricks')
            cmd = [bin_path] if bin_path else []
            status = 'Launching Winetricks...'
            missing = 'Winetricks is not installed.'
        elif tool == 'winecfg':
            bin_path = str(info.get('wine_bin') or '').strip() or shutil.which('wine-staging') or shutil.which('wine') or shutil.which('wine64')
            cmd = [bin_path, 'winecfg'] if bin_path else []
            status = 'Launching winecfg...'
            missing = 'Wine is not installed.'
        else:
            self.set_status(f'Unknown application runtime tool: {tool}')
            return
        if not cmd:
            try:
                self._show_error('Application Runtime', missing)
            except Exception:
                pass
            self.set_status(missing)
            return
        try:
            subprocess.Popen(cmd, cwd=str(prefix), env=env)
            self.set_status(status)
            if text_var is not None:
                text_var.set(self._application_runtime_summary())
        except Exception as exc:
            try:
                self._show_error('Application Runtime', str(exc))
            except Exception:
                pass
            self.set_status(f'Could not launch runtime tool: {exc}')

    def open_options(self):
        existing = getattr(self, "options_window", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except Exception:
            pass

        win = tk.Toplevel(self.root)
        self.options_window = win
        self._style_toplevel(win, title="Options", geometry="1500x980")
        try:
            self.root.update_idletasks()
            root_x = self.root.winfo_rootx()
            root_y = self.root.winfo_rooty()
            self._move_window_to_primary(win, width=1500, height=980, offset_x=24, offset_y=24)
        except Exception:
            pass
        win.minsize(1440, 920)
        try:
            win.transient(self.root)
        except Exception:
            pass

        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="Options", style="Title.TLabel").pack(anchor="w")

        copy_var = tk.BooleanVar(value=bool(self.store.data.get("copy_into_library")))
        autostart_var = tk.BooleanVar(value=bool(self.store.data.get("autostart")))
        preview_var = tk.BooleanVar(value=bool(self.store.data.get("preview_visible", True)))
        pause_on_fullscreen_var = tk.BooleanVar(value=bool(self.store.data.get("pause_on_fullscreen", True)))
        we_var = tk.BooleanVar(value=bool(self.store.data.get("we_enabled", True)))
        show_unsupported_var = tk.BooleanVar(value=bool(self.store.data.get("show_unsupported_we", False)))
        volume_var = tk.IntVar(value=int(self.store.data.get("video_volume", 35)))
        mute_var = tk.BooleanVar(value=bool(self.store.data.get("video_mute", True)))
        sync_monitors_var = tk.BooleanVar(value=bool(self.store.data.get("monitor_sync_mode", True)))
        monitor_mode_var = tk.StringVar(value=str(self.monitor_mode.get() or self.store.data.get("monitor_mode", "shared" if sync_monitors_var.get() else "per_monitor")))
        start_minimized_launch_var = tk.BooleanVar(value=bool(self.store.data.get("start_minimized_launch", self.store.data.get("start_minimized", False))))
        start_minimized_autostart_var = tk.BooleanVar(value=bool(self.store.data.get("start_minimized_autostart", self.store.data.get("start_minimized", False))))
        close_to_tray_var = tk.BooleanVar(value=bool(self.store.data.get("close_to_tray", True)))
        tray_close_notice_var = tk.BooleanVar(value=bool(self.store.data.get("tray_close_notice", True)))
        detected_monitors = ", ".join([self._monitor_display_name(m) for m in self.monitors]) or "None detected"
        selected_monitor_names = set(self._selected_monitor_names())
        options_snapshot_store = copy.deepcopy(self.store.data)
        options_saved = {"done": False}
        live_mode_seed = str(self.monitor_mode.get() or self.store.data.get("monitor_mode", "shared") or "shared")
        if len(self._available_monitor_names()) <= 1:
            live_mode_seed = "shared"
        live_preview_state = {"monitor_mode": live_mode_seed, "playlist_target": str(self.playlist_target.get() or self.store.data.get("playlist_target", "synced") or "synced")}
        snapshot_audio_enabled = list(self.controller.video_audio_enabled_monitors or self._audio_enabled_monitors())
        snapshot_audio_volume = int(self.store.data.get("video_volume", 35))
        snapshot_audio_mute = bool(self.store.data.get("video_mute", True))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True, pady=(0, 4))
        notebook = ttk.Notebook(body, style="MWS.TNotebook")
        notebook.pack(fill="both", expand=True, pady=(0, 6))

        def tab_frame(title: str):
            frame = ttk.Frame(notebook, style="Card.TFrame", padding=8)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(99, weight=1)
            notebook.add(frame, text=title)
            return frame

        def section(parent, title, row, column=0, columnspan=1):
            box = ttk.LabelFrame(parent, text=f" {title} ")
            box.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=(0 if column == 0 else 6, 0), pady=(0, 8))
            return box

        general_tab = tab_frame("General")
        playback_tab = tab_frame("Playback")
        applications_tab = tab_frame("Applications")
        for compact_tab in (general_tab, playback_tab, applications_tab):
            compact_tab.columnconfigure(0, weight=1)
            compact_tab.columnconfigure(1, weight=1)

        general_box = section(general_tab, "Library & preview", 0, 0)
        ttk.Checkbutton(general_box, text="Show preview panel", variable=preview_var).pack(anchor="w", padx=8, pady=(6, 2))
        ttk.Checkbutton(general_box, text="Copy imported files into the internal library", variable=copy_var).pack(anchor="w", padx=8, pady=2)
        
        fullscreen_box = section(general_tab, "Fullscreen behavior", 0, 1)
        ttk.Checkbutton(
            fullscreen_box,
            text="Pause video wallpaper while a fullscreen window is active (X11)",
            variable=pause_on_fullscreen_var,
        ).pack(anchor="w", padx=8, pady=(6, 3))
        ttk.Label(fullscreen_box, text="Pause video wallpapers when a game or browser goes fullscreen.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        startup_box = section(general_tab, "Startup", 1, 0)
        ttk.Checkbutton(startup_box, text="Start automatically on login", variable=autostart_var).pack(anchor="w", padx=8, pady=(6, 2))
        ttk.Checkbutton(startup_box, text="Start minimized when launched manually", variable=start_minimized_launch_var).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(startup_box, text="Start minimized on system startup", variable=start_minimized_autostart_var).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(startup_box, text="Keep app running in tray when clicking X", variable=close_to_tray_var).pack(anchor="w", padx=10, pady=(2, 2))
        ttk.Checkbutton(startup_box, text="Show a tray message when the window is closed to the applet", variable=tray_close_notice_var).pack(anchor="w", padx=10, pady=(2, 2))

        audio_box = section(playback_tab, "Video wallpaper audio", 0, 0)
        ttk.Label(audio_box, text="Choose how video wallpaper audio should behave.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(8, 4))
        mute_toggle = ttk.Checkbutton(
            audio_box,
            text="Mute everything",
            variable=mute_var,
        )
        mute_toggle.pack(anchor="w", padx=8, pady=(0, 6))
        ttk.Label(audio_box, text="Mutes all video wallpaper sound and locks the monitor audio choices below.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 6))
        ttk.Label(audio_box, text="Volume", style="PanelBody.TLabel").pack(anchor="w", padx=8, pady=(0, 2))
        vol_row = ttk.Frame(audio_box)
        vol_row.pack(fill="x", padx=8, pady=(0, 8))
        volume_scale = ttk.Scale(
            vol_row,
            from_=0,
            to=100,
            variable=volume_var,
            orient="horizontal",
            command=lambda _=None: (
                self._apply_audio_settings(
                    volume=int(volume_var.get()),
                    mute=bool(mute_var.get()),
                    save=False,
                    reapply=True
                ),
            ),
        )
        volume_scale.pack(side="left", fill="x", expand=True, padx=(0, 10))
        volume_value_label = ttk.Label(vol_row, textvariable=volume_var, style="PanelBody.TLabel", width=4)
        volume_value_label.pack(side="left")
        ttk.Label(audio_box, text="Applies only to video wallpapers.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))
        audio_mon_box = ttk.LabelFrame(audio_box, text=" Monitor audio ")
        audio_mon_box.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(audio_mon_box, text="Choose which monitors are allowed to play video sound. By default only the primary monitor plays audio.", style="PanelMuted.TLabel", wraplength=390, justify="left").pack(anchor="w", padx=8, pady=(8, 6))
        audio_monitor_vars = {}
        enabled_audio = set(self._audio_enabled_monitors())
        audio_monitor_checks = []

        def _selected_audio_monitor_names():
            return [name for name, var in audio_monitor_vars.items() if bool(var.get())]

        def _apply_live_audio_from_options(save: bool = False):
            chosen = [name for name in _selected_audio_monitor_names() if name in self._available_monitor_names()]
            if not chosen and self._available_monitor_names():
                chosen = [self._primary_monitor_name()]
            self.store.data["audio_enabled_monitors"] = list(chosen)
            try:
                self.controller.set_audio_monitor_enabled(list(chosen))
            except Exception:
                pass
            self._apply_audio_settings(
                volume=int(volume_var.get()),
                mute=bool(mute_var.get()),
                save=save,
                reapply=True,
            )

        for mon in self.monitors:
            mon_name = self._monitor_display_name(mon)
            flag = tk.BooleanVar(value=(mon_name in enabled_audio))
            audio_monitor_vars[mon_name] = flag
            label = mon_name + (" (primary)" if isinstance(mon, dict) and mon.get("primary") else "")
            chk = ttk.Checkbutton(audio_mon_box, text=label, variable=flag, command=lambda: _apply_live_audio_from_options(save=False))
            chk.pack(anchor="w", padx=8, pady=2)
            audio_monitor_checks.append(chk)

        def _refresh_audio_lock(*_args):
            disabled = bool(mute_var.get())
            desired = "disabled" if disabled else "normal"
            for widget in [volume_scale, volume_value_label, audio_mon_box]:
                try:
                    widget.configure(state=desired)
                except Exception:
                    pass
            for chk in audio_monitor_checks:
                try:
                    chk.configure(state=desired)
                except Exception:
                    pass
            _apply_live_audio_from_options(save=False)

        mute_toggle.configure(command=_refresh_audio_lock)
        _refresh_audio_lock()

        auto_box = section(playback_tab, "Auto change", 0, 1)
        ttk.Label(auto_box, text="Automatically change wallpapers after a timer.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(8, 4))

        _stored_auto_per_monitor_pref = bool(self.store.data.get("auto_change_per_monitor_preference", self.store.data.get("auto_change_per_monitor_enabled", False)))
        auto_per_monitor_enabled_var = tk.BooleanVar(value=_stored_auto_per_monitor_pref)
        auto_per_monitor_preference = {"value": bool(auto_per_monitor_enabled_var.get())}
        per_auto_saved = dict(self.store.data.get("auto_change_per_monitor", {}) or {})
        per_auto_vars = {}
        per_monitor_active_tab = tk.StringVar(value="")

        mode_label_map = {"off": "Off", "playlist": "Playlist order", "random": "Random"}
        mode_value_map = {v: k for k, v in mode_label_map.items()}

        auto_shared_info = ttk.Label(auto_box, text="Use one shared auto change rule for the current monitor setup.", style="PanelMuted.TLabel", wraplength=420, justify="left")
        auto_shared_info.pack(anchor="w", padx=8, pady=(0, 6))

        auto_mode_scope = ttk.LabelFrame(auto_box, text=" Auto change setup ")
        auto_mode_scope.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Radiobutton(auto_mode_scope, text="Use one setting for all monitors", value=False, variable=auto_per_monitor_enabled_var).pack(anchor="w", padx=8, pady=(8, 2))
        ttk.Radiobutton(auto_mode_scope, text="Configure separately for each monitor", value=True, variable=auto_per_monitor_enabled_var).pack(anchor="w", padx=8, pady=(2, 8))

        shared_auto_box = ttk.LabelFrame(auto_box, text=" Shared auto change ")
        shared_auto_box.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(shared_auto_box, text="These settings change the current monitor setup together.", style="PanelMuted.TLabel", wraplength=390, justify="left").pack(anchor="w", padx=8, pady=(8, 6))
        ttk.Label(shared_auto_box, text="Mode", style="PanelBody.TLabel").pack(anchor="w", padx=8, pady=(0, 2))
        auto_mode_row = ttk.Frame(shared_auto_box)
        auto_mode_row.pack(fill="x", padx=8, pady=(0, 6))
        for value, label in (("off", "Off"), ("playlist", "Playlist order"), ("random", "Random")):
            ttk.Radiobutton(auto_mode_row, text=label, value=value, variable=self.auto_mode_var, command=self._auto_controls_changed).pack(side="left", padx=(0, 12), pady=2)
        interval_row = ttk.Frame(shared_auto_box)
        interval_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(interval_row, text="Interval", style="PanelBody.TLabel", width=10).pack(side="left")
        self.auto_interval_spin = ttk.Spinbox(interval_row, from_=1, to=1440, textvariable=self.auto_interval_var, width=7, command=self._auto_controls_changed)
        self.auto_interval_spin.pack(side="left", padx=(0, 8))
        self.auto_interval_spin.bind("<KeyRelease>", lambda e: self._auto_controls_changed())
        ttk.Label(interval_row, text="minutes", style="PanelMuted.TLabel").pack(side="left")

        permon_wrap = ttk.LabelFrame(auto_box, text=" Per-monitor auto change ")
        ttk.Label(permon_wrap, text="Pick a monitor tab and choose how that monitor should auto change.", style="PanelMuted.TLabel", wraplength=390, justify="left").pack(anchor="w", padx=8, pady=(8, 6))
        permon_tabs_bar = tk.Frame(permon_wrap, bg=Theme.PANEL, highlightthickness=0, bd=0)
        permon_tabs_bar.pack(fill="x", padx=8, pady=(0, 0))
        permon_content = ttk.Frame(permon_wrap, style="Card.TFrame")
        permon_content.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        for mon in self.monitors:
            mon_name = self._monitor_display_name(mon)
            row_cfg = dict(per_auto_saved.get(mon_name, {}) or {})
            enabled_var = tk.BooleanVar(value=bool(row_cfg.get("enabled", False)))
            mode_var = tk.StringVar(value=mode_label_map.get(str(row_cfg.get("mode", "off")), "Off"))
            interval_var = tk.IntVar(value=max(1, int(row_cfg.get("interval", self.auto_interval_var.get() or 10))))
            per_auto_vars[mon_name] = {"enabled": enabled_var, "mode": mode_var, "interval": interval_var, "primary": False}
            enabled_var.trace_add("write", lambda *_: _persist_option_auto_change_preview())
            mode_var.trace_add("write", lambda *_: _persist_option_auto_change_preview())
            interval_var.trace_add("write", lambda *_: _persist_option_auto_change_preview())
        for mon in self.monitors:
            mon_name = self._monitor_display_name(mon)
            per_auto_vars[mon_name]["primary"] = bool(isinstance(mon, dict) and mon.get("primary"))

        def _render_per_monitor_panel():
            for child in permon_content.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass
            names = list(per_auto_vars.keys())
            if not names:
                ttk.Label(permon_content, text="No monitors detected.", style="PanelMuted.TLabel").grid(row=0, column=0, sticky="w", padx=8, pady=(10, 10))
                return
            active = per_monitor_active_tab.get()
            if active not in names:
                active = names[0]
                per_monitor_active_tab.set(active)
            cfg = per_auto_vars[active]
            permon_content.columnconfigure(1, weight=1)
            ttk.Label(permon_content, text="Mode", style="PanelBody.TLabel").grid(row=0, column=0, sticky="w", padx=8, pady=(10, 6))
            mode_box_pm = ttk.Combobox(permon_content, state="readonly", width=18, values=list(mode_label_map.values()), textvariable=cfg["mode"])
            mode_box_pm.grid(row=0, column=1, sticky="w", padx=8, pady=(10, 6))
            mode_box_pm.bind("<<ComboboxSelected>>", lambda e: self._auto_controls_changed())
            ttk.Label(permon_content, text="Interval (min)", style="PanelBody.TLabel").grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))
            spin = ttk.Spinbox(permon_content, from_=1, to=1440, width=8, textvariable=cfg["interval"], command=self._auto_controls_changed)
            spin.grid(row=1, column=1, sticky="w", padx=8, pady=(0, 8))
            spin.bind("<KeyRelease>", lambda e: self._auto_controls_changed())
            ttk.Label(permon_content, text="Choose Off in Mode if this monitor should keep its current wallpaper.", style="PanelMuted.TLabel", wraplength=340, justify="left").grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 10))

        def _render_per_monitor_tabs():
            names = list(per_auto_vars.keys())
            active = per_monitor_active_tab.get()
            if active not in names and names:
                primary = next((name for name in names if per_auto_vars[name].get("primary")), names[0])
                per_monitor_active_tab.set(primary)
                active = primary
            for child in permon_tabs_bar.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass
            for name in names:
                is_active = (name == active)
                label = f"{name}{' (primary)' if per_auto_vars[name].get('primary') else ''}"
                btn = tk.Button(
                    permon_tabs_bar,
                    text=label,
                    relief="flat",
                    bd=1,
                    padx=12,
                    pady=8,
                    highlightthickness=1,
                    highlightbackground=Theme.BORDER,
                    highlightcolor=Theme.BORDER,
                    activebackground="#18355d",
                    activeforeground=Theme.FG,
                    bg=Theme.ACCENT if is_active else Theme.PANEL_ALT,
                    fg=("#06101f" if is_active else Theme.FG),
                    command=lambda n=name: (per_monitor_active_tab.set(n), _render_per_monitor_tabs(), _render_per_monitor_panel()),
                )
                btn.pack(side="left", padx=(0, 4))

        def _refresh_auto_scope_ui(*_args):
            selected_mode = monitor_mode_var.get() or "shared"
            self.auto_change_scope_var.set("workspace")
            allow_per_monitor = selected_mode == "per_monitor"
            use_per_monitor = allow_per_monitor and bool(auto_per_monitor_enabled_var.get())

            if allow_per_monitor:
                if not auto_mode_scope.winfo_manager():
                    auto_mode_scope.pack(fill="x", padx=8, pady=(0, 6), before=shared_auto_box)
                if auto_shared_info.winfo_manager():
                    auto_shared_info.pack_forget()
            else:
                auto_per_monitor_preference["value"] = bool(auto_per_monitor_enabled_var.get())
                if auto_mode_scope.winfo_manager():
                    auto_mode_scope.pack_forget()
                if not auto_shared_info.winfo_manager():
                    auto_shared_info.pack(anchor="w", padx=8, pady=(0, 6), before=shared_auto_box)
                use_per_monitor = False

            if use_per_monitor:
                if shared_auto_box.winfo_manager():
                    shared_auto_box.pack_forget()
                if not permon_wrap.winfo_manager():
                    permon_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 6))
                _render_per_monitor_tabs()
                _render_per_monitor_panel()
            else:
                if permon_wrap.winfo_manager():
                    permon_wrap.pack_forget()
                if not shared_auto_box.winfo_manager():
                    shared_auto_box.pack(fill="x", padx=8, pady=(0, 6))
            self._update_auto_change_hint()

        def _persist_option_auto_change_preview(*_args):
            try:
                self.store.data["auto_change_per_monitor_preference"] = bool(auto_per_monitor_enabled_var.get())
                self.store.data["auto_change_per_monitor_enabled"] = bool(auto_per_monitor_enabled_var.get()) if (monitor_mode_var.get() == "per_monitor") else False
                per_data = {}
                for mon_name, cfg in per_auto_vars.items():
                    try:
                        _mode_value = mode_value_map.get(str(cfg["mode"].get()), "off")
                        per_data[mon_name] = {
                            "enabled": (_mode_value != "off"),
                            "mode": _mode_value,
                            "interval": max(1, int(cfg["interval"].get())),
                        }
                    except Exception:
                        per_data[mon_name] = {"enabled": False, "mode": "off", "interval": int(self.auto_interval_var.get() or 10)}
                self.store.data["auto_change_per_monitor"] = per_data
                self.store.save()
            except Exception:
                pass

        def _remember_auto_monitor_choice(*_args):
            auto_per_monitor_preference["value"] = bool(auto_per_monitor_enabled_var.get())
            _persist_option_auto_change_preview()
            _refresh_auto_scope_ui()

        auto_per_monitor_enabled_var.trace_add("write", _remember_auto_monitor_choice)
        self.auto_hint_var = tk.StringVar(value="")
        ttk.Label(auto_box, textvariable=self.auto_hint_var, style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        monitors_box = section(general_tab, "Monitors", 1, 1)
        mode_map = {
            "Same on all monitors": "shared",
            "Different per monitor": "per_monitor",
            "Stretch across monitors": "stretch",
        }
        mode_reverse = {v: k for k, v in mode_map.items()}
        ttk.Label(monitors_box, text="Choose how wallpapers should behave when more than one monitor is connected.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(8, 6))
        ttk.Label(monitors_box, text="Monitor mode", style="PanelBody.TLabel").pack(anchor="w", padx=8, pady=(0, 4))
        mode_box_var = tk.StringVar(value=mode_reverse.get(monitor_mode_var.get(), "Same on all monitors"))
        single_monitor_mode = len(self._available_monitor_names()) <= 1
        if single_monitor_mode:
            mode_box_var.set("Same on all monitors")
            monitor_mode_var.set("shared")
        mode_box = ttk.Combobox(monitors_box, state=("disabled" if single_monitor_mode else "readonly"), width=30, values=list(mode_map.keys()), textvariable=mode_box_var)
        mode_box.pack(anchor="w", padx=8, pady=(0, 4))
        single_monitor_hint_var = tk.StringVar(value=("This setting can only be changed when multiple monitors are connected." if single_monitor_mode else ""))
        ttk.Label(monitors_box, textvariable=single_monitor_hint_var, style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))
        monitors_pick_frame = ttk.Frame(monitors_box)
        monitors_pick_label = ttk.Label(monitors_pick_frame, text="Available displays", style="PanelBody.TLabel")
        monitors_pick_label.pack(anchor="w", padx=0, pady=(2, 4))
        monitors_pick_inner = ttk.Frame(monitors_pick_frame)
        monitors_pick_inner.pack(fill="x", padx=0, pady=(0, 0))
        monitor_vars = {}
        for mon in self.monitors:
            mon_name = self._monitor_display_name(mon)
            var = tk.BooleanVar(value=(mon_name in selected_monitor_names))
            monitor_vars[mon_name] = var
            label = mon_name + (" (primary)" if isinstance(mon, dict) and mon.get("primary") else "")
            ttk.Checkbutton(monitors_pick_inner, text=label, variable=var).pack(anchor="w", pady=2)
        monitors_help_var = tk.StringVar(value="Same on all mirrors one wallpaper on every monitor. Different per monitor lets each display use its own wallpaper. Stretch spans one wallpaper across the whole desktop.")
        monitors_help = ttk.Label(monitors_box, textvariable=monitors_help_var, style="PanelMuted.TLabel", wraplength=420, justify="left")
        monitors_help.pack(anchor="w", padx=8, pady=(0, 8))

        _monitor_visibility_state = {"mode": None}
        def _show_monitor_selection(show: bool):
            if show:
                if not monitors_pick_frame.winfo_manager():
                    monitors_pick_frame.pack(fill="x", padx=8, pady=(2, 6), before=monitors_help)
            else:
                if monitors_pick_frame.winfo_manager():
                    monitors_pick_frame.pack_forget()

        def _refresh_monitor_option_visibility(*_args):
            if len(self._available_monitor_names()) <= 1:
                selected_mode = "shared"
                selected_label = "Same on all monitors"
                if mode_box_var.get() != selected_label:
                    mode_box_var.set(selected_label)
                try:
                    mode_box.configure(state="disabled")
                except Exception:
                    pass
                single_monitor_hint_var.set("This setting can only be changed when multiple monitors are connected.")
            else:
                selected_label = (mode_box_var.get() or mode_box.get() or "").strip()
                selected_mode = mode_map.get(selected_label, monitor_mode_var.get() or "shared")
                try:
                    mode_box.configure(values=list(mode_map.keys()), state="readonly")
                except Exception:
                    pass
                monitors_help_var.set("Same on all mirrors one wallpaper on every monitor. Different per monitor lets each display use its own wallpaper. Stretch spans one wallpaper across the whole desktop.")
                single_monitor_hint_var.set("")
            selected_media = self.primary_item()
            constraint = self._media_monitor_mode_constraint(selected_media)
            if constraint:
                forced_mode = constraint.get("forced_mode") or selected_mode
                selected_mode = forced_mode
                forced_label = mode_reverse.get(selected_mode, "Same on all monitors")
                values = [forced_label]
                try:
                    mode_box.configure(values=values, state="disabled")
                except Exception:
                    pass
                mode_box_var.set(forced_label)
                monitors_help_var.set(constraint.get("hint") or monitors_help_var.get())
            previous_mode = _monitor_visibility_state["mode"]
            _monitor_visibility_state["mode"] = selected_mode
            if monitor_mode_var.get() != selected_mode:
                monitor_mode_var.set(selected_mode)
            expected_label = mode_reverse.get(selected_mode, "Same on all monitors")
            if mode_box_var.get() != expected_label:
                mode_box_var.set(expected_label)
            _show_monitor_selection(selected_mode == "per_monitor")
            if selected_mode == "per_monitor":
                auto_per_monitor_enabled_var.set(bool(auto_per_monitor_preference["value"]))
            elif previous_mode == "per_monitor":
                auto_per_monitor_preference["value"] = bool(auto_per_monitor_enabled_var.get())
                auto_per_monitor_enabled_var.set(False)
            target_value = self.playlist_target.get() or live_preview_state.get("playlist_target") or "synced"
            if selected_mode != "per_monitor":
                target_value = "synced"
            if self.monitor_mode.get() != selected_mode:
                self.monitor_mode.set(selected_mode)
            if self.store.data.get("monitor_mode") != selected_mode:
                self.store.data["monitor_mode"] = selected_mode
            if self.store.data.get("monitor_sync_mode") != (selected_mode != "per_monitor"):
                self.store.data["monitor_sync_mode"] = (selected_mode != "per_monitor")
            self.monitor_sync_mode.set(selected_mode != "per_monitor")
            if self.playlist_target.get() != target_value:
                self.playlist_target.set(target_value)
            self.store.data["playlist_target"] = target_value
            try:
                if hasattr(self, "monitor_mode_box"):
                    self.monitor_mode_box.set(self._monitor_mode_label(selected_mode))
            except Exception:
                pass
            self._refresh_target_box()
            if previous_mode is not None and previous_mode != selected_mode:
                try:
                    self._apply_monitor_mode_change_live(previous_mode, selected_mode)
                except Exception:
                    pass
                try:
                    self._trigger_random_refresh_on_monitor_mode_change("settings_live")
                except Exception:
                    pass
                live_preview_state["monitor_mode"] = selected_mode
                live_preview_state["playlist_target"] = target_value
            _refresh_auto_scope_ui()
            try:
                monitors_box.update_idletasks()
                auto_box.update_idletasks()
                win.update_idletasks()
            except Exception:
                pass

        mode_box.configure(postcommand=lambda: mode_box.configure(values=list(mode_map.keys())))
        mode_box.bind("<<ComboboxSelected>>", _refresh_monitor_option_visibility)
        mode_box_var.trace_add("write", _refresh_monitor_option_visibility)
        _refresh_monitor_option_visibility()

        runtime_box = section(applications_tab, "Application runtime", 0, 0)
        prefix_path_var = tk.StringVar(value="")
        runtime_summary_var = tk.StringVar(value="")

        def _refresh_application_runtime_panel_texts():
            try:
                info = self.controller.get_application_runtime_info()
            except Exception as exc:
                prefix_path_var.set("Application prefix unavailable")
                runtime_summary_var.set(f"Application runtime status unavailable: {exc}")
                return
            prefix_path_var.set(str(info.get('prefix_dir') or '-'))
            runtime_summary_var.set(self._application_runtime_summary_from_info(info))

        self._refresh_application_runtime_panel = _refresh_application_runtime_panel_texts
        _refresh_application_runtime_panel_texts()

        ttk.Label(runtime_box, text="Prefix path", style="PanelMuted.TLabel").pack(anchor="w", padx=8, pady=(8, 2))
        prefix_bar = ttk.Frame(runtime_box)
        prefix_bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(prefix_bar, textvariable=prefix_path_var, style="PanelMuted.TLabel", wraplength=420, justify="left").pack(side="left", fill="x", expand=True)
        ttk.Button(prefix_bar, text="Copy", command=self._copy_application_prefix_path).pack(side="right")
        ttk.Button(prefix_bar, text="Open Folder", command=self._open_application_prefix_folder).pack(side="right", padx=(0, 8))

        ttk.Label(runtime_box, text="Runtime status", style="PanelMuted.TLabel").pack(anchor="w", padx=8, pady=(0, 2))
        ttk.Label(runtime_box, textvariable=runtime_summary_var, style="PanelMuted.TLabel", wraplength=520, justify="left").pack(anchor="w", padx=8, pady=(0, 8))
        runtime_row = ttk.Frame(runtime_box)
        runtime_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(runtime_row, text="Initialize Runtime", command=lambda: self._run_application_runtime_task('init', runtime_summary_var, 'Initializing managed Wine prefix...')).pack(side="left")
        ttk.Button(runtime_row, text="Reset Runtime", command=lambda: self._run_application_runtime_task('reset', runtime_summary_var, 'Resetting managed Wine prefix...')).pack(side="left", padx=(8, 0))
        ttk.Button(runtime_row, text="Run Winetricks", command=lambda: self._launch_application_runtime_tool('winetricks', runtime_summary_var)).pack(side="left", padx=(8, 0))
        ttk.Button(runtime_row, text="Run winecfg", command=lambda: self._launch_application_runtime_tool('winecfg', runtime_summary_var)).pack(side="left", padx=(8, 0))
        tools_row = ttk.Frame(runtime_box)
        tools_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(tools_row, text="Open Terminal Here", command=self._open_application_prefix_terminal).pack(side="left")
        ttk.Label(runtime_box, text="Use these tools to test compatibility inside the managed applications prefix.", style="PanelMuted.TLabel", wraplength=520, justify="left").pack(anchor="w", padx=8, pady=(0, 8))
        app_help = section(applications_tab, "Application support", 0, 1)
        ttk.Label(app_help, text="Experimental support", style="PanelMuted.TLabel").pack(anchor="w", padx=8, pady=(8, 2))
        ttk.Label(app_help, text="Application wallpapers are still experimental. Unity-based apps usually work best.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))
        ttk.Label(app_help, text="Primary monitor only", style="PanelMuted.TLabel").pack(anchor="w", padx=8, pady=(0, 2))
        ttk.Label(app_help, text="Applications currently launch only on the primary monitor.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))
        ttk.Label(app_help, text="Tip", style="PanelMuted.TLabel").pack(anchor="w", padx=8, pady=(0, 2))
        ttk.Label(app_help, text="If one app behaves badly, turn it off in the library until you want to test it again.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        we_box = section(general_tab, "Wallpaper Engine integration", 2, 0)
        ttk.Checkbutton(we_box, text="Enable Wallpaper Engine library integration", variable=we_var).pack(anchor="w", padx=8, pady=(6, 2))
        we_dep_widgets = []
        show_unsupported_cb = ttk.Checkbutton(we_box, text="Show unsupported Wallpaper Engine items", variable=show_unsupported_var)
        show_unsupported_cb.pack(anchor="w", padx=28, pady=(2, 8))
        we_dep_widgets.append(show_unsupported_cb)
        ttk.Label(we_box, text="Preview and scene inspector data for Wallpaper Engine items depend on the local workshop files and available previews.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

        actions_box = section(general_tab, "App actions", 2, 1)
        ttk.Label(actions_box, text="Quick actions for hiding the app or stopping all wallpaper processes.", style="PanelMuted.TLabel", wraplength=420).pack(anchor="w", padx=10, pady=(8, 6))
        action_row = ttk.Frame(actions_box)
        action_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(action_row, text="Hide to Tray Now", command=self.hide_to_tray).pack(side="left")
        ttk.Button(action_row, text="Quit", command=self.quit_all_instances).pack(side="left", padx=(8, 0))

        ttk.Label(actions_box, text="Hide the app to tray or stop every related wallpaper process.", style="PanelMuted.TLabel", wraplength=420, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

        def refresh_we_controls(*_args):
            enabled = bool(we_var.get())
            state = "normal" if enabled else "disabled"
            for w in we_dep_widgets:
                try:
                    w.configure(state=state)
                except Exception:
                    pass
        we_var.trace_add("write", refresh_we_controls)
        refresh_we_controls()
        def close_options():
            if not options_saved["done"]:
                try:
                    current_live_mode = str(self.monitor_mode.get() or live_preview_state.get("monitor_mode") or "shared")
                    current_live_target = str(self.playlist_target.get() or live_preview_state.get("playlist_target") or "synced")
                    self.store.data = copy.deepcopy(options_snapshot_store)
                    restored_mode = str(self.store.data.get("monitor_mode", "shared") or "shared")
                    restored_target = str(self.store.data.get("playlist_target", "synced") or "synced")
                    self.pause_on_fullscreen_pref.set(bool(self.store.data.get("pause_on_fullscreen", True)))
                    self.pause_on_fullscreen_enabled = bool(self.store.data.get("pause_on_fullscreen", True))
                    self.start_minimized_launch_pref.set(bool(self.store.data.get("start_minimized_launch", self.store.data.get("start_minimized", False))))
                    self.start_minimized_autostart_pref.set(bool(self.store.data.get("start_minimized_autostart", self.store.data.get("start_minimized", False))))
                    self.close_to_tray_pref.set(bool(self.store.data.get("close_to_tray", True)))
                    self.preview_enabled.set(bool(self.store.data.get("preview_visible", True)))
                    self.show_unsupported_we.set(bool(self.store.data.get("show_unsupported_we", False)))
                    self.monitor_mode.set(restored_mode)
                    self.playlist_target.set(restored_target)
                    self.auto_mode_var.set(str(self.store.data.get("auto_change_mode", "off")))
                    self.auto_interval_var.set(int(self.store.data.get("random_interval_minutes", 10)))
                    self.auto_change_scope_var.set(str(self.store.data.get("auto_change_scope", "workspace")))
                    self.controller.set_audio_monitor_enabled(list(snapshot_audio_enabled))
                    self.controller.set_audio_options(snapshot_audio_volume, snapshot_audio_mute)
                    self.controller.apply_audio_live()
                    self._refresh_target_box()
                    try:
                        if hasattr(self, "monitor_mode_box"):
                            self.monitor_mode_box.set(self._monitor_mode_label(restored_mode))
                    except Exception:
                        pass
                    if current_live_mode != restored_mode:
                        try:
                            self._apply_monitor_mode_change_live(current_live_mode, restored_mode)
                        except Exception:
                            pass
                    self._apply_preview_visibility()
                    self._start_random_if_enabled()
                    self.refresh_list()
                    self._update_pause_button()
                except Exception:
                    pass
            self.options_window = None
            try:
                win.destroy()
            except Exception:
                pass

        def save_options():
            options_saved["done"] = True
            we_was_enabled = bool(self.store.data.get("we_enabled", True))
            old_selected_monitors = set(self._selected_monitor_names())
            old_monitor_mode = str(self.store.data.get("monitor_mode", self.monitor_mode.get() or "shared") or "shared")

            self.store.data["copy_into_library"] = copy_var.get()
            self.store.data["autostart"] = autostart_var.get()
            self.store.data["preview_visible"] = preview_var.get()
            self.store.data["pause_on_fullscreen"] = pause_on_fullscreen_var.get()
            self.pause_on_fullscreen_pref.set(pause_on_fullscreen_var.get())
            self.pause_on_fullscreen_enabled = bool(pause_on_fullscreen_var.get())
            self.store.data["we_enabled"] = we_var.get()
            self.store.data["show_unsupported_we"] = show_unsupported_var.get() if we_var.get() else False
            self.store.data["video_volume"] = int(volume_var.get())
            self.store.data["video_mute"] = mute_var.get()
            self.store.data["auto_change_mode"] = self.auto_mode_var.get()
            self.store.data["random_interval_minutes"] = int(self.auto_interval_var.get())
            selected_mode = ("shared" if len(self._available_monitor_names()) <= 1 else (monitor_mode_var.get() or "shared"))
            self.store.data["auto_change_scope"] = "workspace"
            self.store.data["monitor_mode"] = selected_mode
            self.monitor_mode.set(selected_mode)
            self.store.data["monitor_sync_mode"] = (selected_mode != "per_monitor")
            self.monitor_sync_mode.set(self.store.data["monitor_sync_mode"])
            if selected_mode != "per_monitor":
                self.store.data["playlist_target"] = "synced"
                self.playlist_target.set("synced")
            self.store.data["start_minimized_launch"] = start_minimized_launch_var.get()
            self.start_minimized_launch_pref.set(start_minimized_launch_var.get())
            self.store.data["start_minimized_autostart"] = start_minimized_autostart_var.get()
            self.start_minimized_autostart_pref.set(start_minimized_autostart_var.get())
            self.store.data["start_minimized"] = bool(start_minimized_launch_var.get() or start_minimized_autostart_var.get())
            self.store.data["close_to_tray"] = close_to_tray_var.get()
            self.close_to_tray_pref.set(close_to_tray_var.get())
            self.store.data["tray_close_notice"] = tray_close_notice_var.get()
            self.store.data.pop("tray_menu_peek", None)

            chosen_monitors = [name for name, var in monitor_vars.items() if bool(var.get())]
            available_now = self._available_monitor_names()
            chosen_monitors = [name for name in chosen_monitors if name in available_now]
            self.store.data["selected_monitors"] = list(chosen_monitors)
            chosen_audio_monitors = [name for name, var in locals().get("audio_monitor_vars", {}).items() if bool(var.get()) and name in available_now]
            if not chosen_audio_monitors and available_now:
                chosen_audio_monitors = [self._primary_monitor_name()]
            self.store.data["audio_enabled_monitors"] = list(chosen_audio_monitors)
            try:
                self.controller.set_audio_monitor_enabled(list(chosen_audio_monitors))
            except Exception:
                pass
            if "auto_per_monitor_enabled_var" in locals():
                self.store.data["auto_change_per_monitor_preference"] = bool(locals().get("auto_per_monitor_enabled_var").get())
            self.store.data["auto_change_per_monitor_enabled"] = bool(locals().get("auto_per_monitor_enabled_var").get()) if ("auto_per_monitor_enabled_var" in locals() and selected_mode == "per_monitor") else False
            if "per_auto_vars" in locals():
                per_data = {}
                for mon_name, cfg in per_auto_vars.items():
                    try:
                        _mode_value = mode_value_map.get(str(cfg["mode"].get()), "off")
                        per_data[mon_name] = {
                            "enabled": (_mode_value != "off"),
                            "mode": _mode_value,
                            "interval": max(1, int(cfg["interval"].get())),
                        }
                    except Exception:
                        per_data[mon_name] = {"enabled": False, "mode": "off", "interval": int(self.auto_interval_var.get() or 10)}
                self.store.data["auto_change_per_monitor"] = per_data
            new_selected_monitors = set(chosen_monitors)
            removed_monitors = old_selected_monitors - new_selected_monitors

            self.preview_enabled.set(preview_var.get())
            self.show_unsupported_we.set(bool(self.store.data["show_unsupported_we"]))
            self.controller.set_audio_options(int(self.store.data["video_volume"]), bool(self.store.data["video_mute"]))
            try:
                self.controller.apply_audio_live()
            except Exception:
                pass
            if we_was_enabled and not we_var.get():
                self.we_items = []
                self.store.set_items(self.we_items, "we_items")

            if removed_monitors:
                try:
                    self.controller.stop_video()
                    self._update_pause_button()
                except Exception:
                    pass

            old_auto_signature = (
                str(options_snapshot_store.get("monitor_mode", self.monitor_mode.get() or "shared") or "shared"),
                str(options_snapshot_store.get("auto_change_mode", self.auto_mode_var.get() or "off") or "off"),
                int(options_snapshot_store.get("random_interval_minutes", self.auto_interval_var.get() or 10) or 10),
                bool(options_snapshot_store.get("auto_change_per_monitor_enabled", False)),
                bool(options_snapshot_store.get("auto_change_per_monitor_preference", False)),
                repr(dict(options_snapshot_store.get("auto_change_per_monitor", {}) or {})),
            )
            new_auto_signature = (
                str(self.store.data.get("monitor_mode", self.monitor_mode.get() or "shared") or "shared"),
                str(self.store.data.get("auto_change_mode", self.auto_mode_var.get() or "off") or "off"),
                int(self.store.data.get("random_interval_minutes", self.auto_interval_var.get() or 10) or 10),
                bool(self.store.data.get("auto_change_per_monitor_enabled", False)),
                bool(self.store.data.get("auto_change_per_monitor_preference", False)),
                repr(dict(self.store.data.get("auto_change_per_monitor", {}) or {})),
            )

            self.store.save()
            self._refresh_target_box()
            try:
                if hasattr(self, "monitor_mode_box"):
                    self.monitor_mode_box.set(self._monitor_mode_label(selected_mode))
            except Exception:
                pass
            self._apply_monitor_mode_change_live(old_monitor_mode, selected_mode)
            if old_monitor_mode != selected_mode:
                self._trigger_random_refresh_on_monitor_mode_change("options_save")
            self._write_autostart()
            self._apply_we_visibility()
            self._apply_preview_visibility()
            if old_auto_signature != new_auto_signature:
                self._apply_auto_scheduler_changes(old_auto_signature, new_auto_signature)
            else:
                try:
                    self._schedule_next_auto_tick()
                except Exception:
                    pass
            self.refresh_list()
            self._update_pause_button()
            if removed_monitors:
                self.set_status("Disabled monitor(s) saved. Active video wallpaper was stopped so it no longer shows on removed displays.")
            close_options()

        footer = ttk.Frame(outer)
        footer.pack(fill="x", side="bottom", pady=(10, 0))
        ttk.Button(footer, text="Cancel", command=close_options).pack(side="left", ipadx=14, ipady=5)
        ttk.Button(footer, text="Save", style="Accent.TButton", command=save_options).pack(side="right", ipadx=18, ipady=5)
        win.protocol("WM_DELETE_WINDOW", close_options)

    def toggle_preview(self):

        value = not self.preview_enabled.get()
        self.preview_enabled.set(value)
        self.store.data["preview_visible"] = value
        self.store.save()
        self._apply_preview_visibility()
        if value:
            self.on_select()

    def open_selected_folder(self):
        item = self.primary_item()
        if item:
            open_in_file_manager(Path(item.path))

    def remove_selected(self):
        sel = self.selected_items()
        if not sel:
            return
        local_paths = {Path(i.path) for i in sel if i.source == "local"}
        we_paths = {Path(i.path) for i in sel if i.source == "wallpaper_engine"}
        self.items = [i for i in self.items if Path(i.path) not in local_paths]
        self.we_items = [i for i in self.we_items if Path(i.path) not in we_paths]
        self._persist_items()
        self.refresh_list()
        self.set_status(f"Removed {len(sel)} item(s)")

    def clear_local(self):
        if not self._ask_yes_no(APP_NAME, "Remove all local library entries?"):
            return
        self.items = []
        self._persist_items()
        self.refresh_list()

    def clear_all(self):
        if not self._ask_yes_no(APP_NAME, "Remove all local and Wallpaper Engine entries from the library view?"):
            return
        self.items = []
        self.we_items = []
        self._persist_items()
        self.refresh_list()

    def reset_view(self):
        self.search_var.set("")
        self.sort_var.set("playlist")
        self.tab_var.set("all")
        self.store.data["sort_mode"] = "playlist"
        self.store.data["active_tab"] = "all"
        self.store.save()
        self._refresh_tab_buttons()
        self.refresh_list()

    def sync_we(self):
        if not self.store.data.get("we_enabled", True):
            self._show_info(APP_NAME, "Wallpaper Engine integration is disabled in Options.")
            return
        items, roots = sync_wallpaper_engine(show_unsupported=bool(self.show_unsupported_we.get()))
        for item in items:
            if not getattr(item, "supported", True):
                item.enabled = False
        self._show_we_sync_popup(items, roots)


    def _show_we_sync_popup(self, scanned_items, roots):
        existing = list(self.we_items)
        existing_keys = {self._we_item_key(x): x for x in existing}
        scanned_keys = {self._we_item_key(x): x for x in scanned_items}
        removed = [x for x in existing if self._we_item_key(x) not in scanned_keys]
        steam_type = detect_steam_install_type(roots)

        win = tk.Toplevel(self.root)
        self._style_toplevel(win, title="Wallpaper Engine Sync", geometry="1440x930", modal=True)
        try:
            win.minsize(1380, 880)
        except Exception:
            pass

        outer = ttk.Frame(win, style="Card.TFrame", padding=14)
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer, style="Card.TFrame")
        head.pack(fill="x")
        left_head = ttk.Frame(head, style="Card.TFrame")
        left_head.pack(side="left", fill="x", expand=True)
        ttk.Label(left_head, text="Wallpaper Engine Sync", style="TitlePopup.TLabel").pack(anchor="w")
        tk.Label(
            left_head,
            text="Review, rename, preview, and choose exactly which items should be imported.",
            bg=Theme.PANEL,
            fg=Theme.MUTED,
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(6, 0))

        counts = {}
        for it in scanned_items:
            counts[it.media_type] = counts.get(it.media_type, 0) + 1
        counts_text = " · ".join(f"{k.title()}: {v}" for k, v in sorted(counts.items())) or "No items found"

        chosen_count_var = tk.StringVar(value="0 selected")

        def do_import():
            chosen = []
            for idx, item in enumerate(order):
                if checked[idx].get():
                    if item.media_type in {"application", "html"}:
                        item.enabled = False
                    chosen.append(item)
            self.we_items = chosen
            self.store.data['we_paths'] = [str(p) for p in roots]
            self.store.data['we_last_sync'] = time.time()
            self.store.set_items(self.we_items, 'we_items')
            self.refresh_list()
            self.monitors = list_monitors()
            self._refresh_target_box()
            unsupported_count = sum(1 for x in chosen if not getattr(x, 'supported', True))
            self.set_status(f"Wallpaper Engine sync imported {len(chosen)} item(s), {unsupported_count} unsupported auto-disabled. Steam: {steam_type}")
            win.destroy()

        import_top_btn = tk.Button(
            head,
            text="Import Selected",
            command=do_import,
            bg=Theme.ACCENT,
            fg="#06101f",
            activebackground="#7cb7ff",
            activeforeground="#06101f",
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        import_top_btn.pack(side="right", anchor="ne")

        badges = tk.Frame(outer, bg=Theme.PANEL)
        badges.pack(fill="x", pady=(12, 8))

        def add_badge(text, accent=False):
            bg = Theme.ACCENT if accent else Theme.PANEL_ALT
            fg = "#06101f" if accent else Theme.FG
            tk.Label(
                badges,
                text=text,
                bg=bg,
                fg=fg,
                font=("Segoe UI", 10, "bold"),
                padx=10,
                pady=6,
                bd=1,
                relief="solid",
                highlightthickness=0,
            ).pack(side="left", padx=(0, 8))

        add_badge(f"Steam source: {steam_type}", accent=True)
        add_badge(f"Workshop paths: {len(roots)}")
        add_badge(f"Found: {len(scanned_items)}")
        add_badge(counts_text)
        add_badge(f"Removed since last sync: {len(removed)}")

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(0, 4))
        left = ttk.Frame(body, style="Card.TFrame", padding=10)
        right = ttk.Frame(body, style="Alt.TFrame", padding=10)
        body.add(left, weight=6)
        body.add(right, weight=4)

        topbar = ttk.Frame(left, style="Card.TFrame")
        topbar.pack(fill="x", pady=(0, 8))
        ttk.Label(topbar, text="Items to import", style="Body.TLabel").pack(side="left")
        ttk.Label(topbar, text="Click Add to toggle. Double-click Name to rename. Double-click row to preview.", style="Muted.TLabel").pack(side="right")

        cols = ("use", "type", "name", "status")
        tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse", height=18)
        for col, width, anchor in (("use", 92, "center"), ("type", 100, "center"), ("name", 440, "w"), ("status", 110, "center")):
            title = {"use": "Add", "type": "Type", "name": "Name", "status": "Status"}[col]
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor=anchor, stretch=(col == "name"))
        list_wrap = ttk.Frame(left, style="Card.TFrame")
        list_wrap.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(list_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        preview_wrap = tk.Frame(right, bg=Theme.PANEL_ALT, highlightbackground=Theme.BORDER, highlightthickness=1)
        preview_wrap.pack(fill="x", pady=(0, 8))
        preview_label = tk.Label(
            preview_wrap,
            bg="#07111f",
            fg="#d7e7ff",
            text="Select an item",
            font=("Segoe UI", 18, "bold"),
            cursor="hand2",
            padx=10,
            pady=10,
        )
        preview_label.pack(fill="both", expand=True, ipady=22)
        tk.Label(
            right,
            text="Preview & details",
            bg=Theme.PANEL_ALT,
            fg=Theme.FG,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(2, 6))
        detail_text = tk.Text(right, height=8, wrap="word", bg="#07111f", fg="#d7e7ff", insertbackground="#d7e7ff", relief="flat", padx=10, pady=10)
        detail_text.pack(fill="both", expand=True)
        detail_text.configure(state="disabled")

        editor = ttk.Frame(outer, style="Card.TFrame")
        editor.pack(fill="x", pady=(8, 0))
        ttk.Label(editor, text="Rename selected item", style="Body.TLabel").pack(side="left")
        name_var = tk.StringVar()
        name_ent = ttk.Entry(editor, textvariable=name_var, width=56)
        name_ent.pack(side="left", padx=(10, 8), fill="x", expand=True)

        checked = {}
        order = list(scanned_items)
        for idx, item in enumerate(order):
            checked[idx] = tk.BooleanVar(value=True)
            status = "New" if self._we_item_key(item) not in existing_keys else "Update"
            tree.insert("", "end", iid=str(idx), values=("☑ Yes", item.media_type.title(), item.name, status))

        popup_preview = {"img": None}
        edit_box = {"widget": None, "idx": None}

        def refresh_row(idx):
            item = order[idx]
            status = "New" if self._we_item_key(item) not in existing_keys else "Update"
            tree.item(str(idx), values=(("☑ Yes" if checked[idx].get() else "☐ No"), item.media_type.title(), item.name, status))

        def selected_index():
            sel = tree.selection()
            if not sel:
                return None
            try:
                return int(sel[0])
            except Exception:
                return None

        def render_popup_preview(item):
            img_path = None
            p = Path(item.path)
            if item.media_type == "video":
                img_path = render_video_thumbnail_file(p, (430, 245))
            elif item.media_type == "html":
                hp = find_html_preview_image(p)
                if hp is not None:
                    img_path = render_image_preview_file(hp, (430, 245))
            elif item.media_type == "application":
                pp = Path(getattr(item, "preview_path", "") or "")
                if pp.exists():
                    img_path = render_image_preview_file(pp, (430, 245))
            else:
                img_path = render_image_preview_file(p, (430, 245))
            if img_path is not None and Path(img_path).exists():
                try:
                    popup_preview["img"] = tk.PhotoImage(file=str(img_path))
                    if item.media_type in {"video", "html"}:
                        preview_label.configure(image=popup_preview["img"], text="▶\nClick to preview", compound="center")
                    else:
                        preview_label.configure(image=popup_preview["img"], text="", compound="center")
                    return
                except Exception:
                    pass
            popup_preview["img"] = None
            if item.media_type in {"video", "html"}:
                preview_label.configure(image="", text="▶\nClick to preview", compound="center")
            else:
                preview_label.configure(image="", text="Preview unavailable", compound="center")

        def update_selection_info():
            total = len(order)
            chosen = sum(1 for idx in range(total) if checked[idx].get())
            chosen_count_var.set(f"{chosen} selected")
            import_top_btn.configure(text=f"Import Selected ({chosen})")

        def update_details(event=None):
            idx = selected_index()
            if idx is None:
                return
            item = order[idx]
            name_var.set(item.name)
            lines = [
                f"Name: {item.name}",
                f"Type: {item.media_type.title()}",
                f"Format: {(item.format or '-').upper()}",
                f"Source: {item.source.replace('_', ' ').title()}",
                f"Path: {item.path}",
                f"Workshop ID: {getattr(item, 'workshop_id', '-') or '-'}",
                f"Notes: {item.notes or '-'}",
                f"Supported: {'Yes' if getattr(item, 'supported', True) else 'No'}",
                f"Will import: {'Yes' if checked[idx].get() else 'No'}",
            ]
            detail_text.configure(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.insert("1.0", "\n".join(lines))
            detail_text.configure(state="disabled")
            render_popup_preview(item)

        def apply_name(*_args):
            idx = selected_index()
            if idx is None:
                return
            new_name = name_var.get().strip()
            if new_name:
                order[idx].name = new_name
                refresh_row(idx)
                update_details()

        def toggle_selected(idx=None):
            if idx is None:
                idx = selected_index()
            if idx is None:
                return
            checked[idx].set(not checked[idx].get())
            refresh_row(idx)
            update_details()
            update_selection_info()

        def on_tree_click(event):
            region = tree.identify("region", event.x, event.y)
            col = tree.identify_column(event.x)
            row = tree.identify_row(event.y)
            if row:
                tree.selection_set(row)
                tree.focus(row)
                win.after_idle(update_details)
            if region == "cell" and col == "#1" and row:
                toggle_selected(int(row))
                return "break"
            return None

        def on_tree_release(event):
            row = tree.identify_row(event.y)
            if row:
                tree.selection_set(row)
                tree.focus(row)
            win.after_idle(update_details)
            return None

        def close_editor(*_args):
            w = edit_box.get("widget")
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
            edit_box["widget"] = None
            edit_box["idx"] = None

        def open_name_editor(event=None):
            row = tree.identify_row(event.y) if event is not None else None
            col = tree.identify_column(event.x) if event is not None else None
            if row and col != "#3":
                return
            idx = int(row) if row else selected_index()
            if idx is None:
                return
            tree.selection_set(str(idx))
            tree.focus(str(idx))
            update_details()
            close_editor()
            bbox = tree.bbox(str(idx), "#3")
            if not bbox:
                return
            x, y, w, h = bbox
            ent = ttk.Entry(tree)
            ent.insert(0, order[idx].name)
            ent.place(x=x+1, y=y+1, width=w-2, height=h-2)
            ent.focus_set()
            ent.selection_range(0, "end")
            edit_box["widget"] = ent
            edit_box["idx"] = idx

            def commit(event=None):
                new_name = ent.get().strip()
                if new_name:
                    order[idx].name = new_name
                    name_var.set(new_name)
                    refresh_row(idx)
                    update_details()
                close_editor()
                return "break"

            ent.bind("<Return>", commit)
            ent.bind("<Escape>", lambda e: (close_editor(), "break")[1])
            ent.bind("<FocusOut>", commit)

        def open_item_preview(event=None):
            idx = selected_index()
            if idx is None:
                return
            item = order[idx]
            p = Path(item.path)
            try:
                try:
                    win.grab_release()
                except Exception:
                    pass
                if item.media_type == "video":
                    self._open_preview_popup(p, parent=win, restore_grab_to=win)
                elif item.media_type == "html":
                    hp = find_html_preview_image(p)
                    if hp is not None and Path(hp).exists():
                        self._open_still_preview_popup(Path(hp), title=f"HTML Preview - {item.name}", parent=win, restore_grab_to=win)
                    else:
                        subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        try:
                            win.grab_set()
                        except Exception:
                            pass
                else:
                    self._open_still_preview_popup(p, title=f"Preview - {item.name}", parent=win, restore_grab_to=win)
                self.set_status(f"Preview popup opened: {item.name}")
            except Exception as exc:
                try:
                    win.grab_set()
                except Exception:
                    pass
                self.set_status(f"Preview open failed: {exc}")

        def on_tree_double(event=None):
            row = tree.identify_row(event.y) if event is not None else None
            col = tree.identify_column(event.x) if event is not None else None
            if row:
                tree.selection_set(row)
                tree.focus(row)
                update_details()
            if col == "#3":
                open_name_editor(event)
            else:
                open_item_preview(event)
            return "break"

        tree.bind("<<TreeviewSelect>>", update_details)
        tree.bind("<Button-1>", on_tree_click)
        tree.bind("<ButtonRelease-1>", on_tree_release, add="+")
        tree.bind("<Double-1>", on_tree_double)
        tree.bind("<Return>", open_item_preview)
        name_ent.bind("<Return>", apply_name)
        preview_label.bind("<Button-1>", open_item_preview)

        if order:
            tree.selection_set("0")
            tree.focus("0")
            update_details()

        actions = ttk.Frame(outer, style="Card.TFrame")
        actions.pack(fill="x", pady=(8, 0))

        footer = tk.Frame(actions, bg=Theme.PANEL_ALT, highlightbackground=Theme.BORDER, highlightthickness=1)
        footer.pack(fill="x")

        left_actions = ttk.Frame(footer, style="Card.TFrame")
        left_actions.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        right_actions = ttk.Frame(footer, style="Card.TFrame")
        right_actions.pack(side="right", padx=10, pady=10)

        ttk.Button(left_actions, text="Check All", command=lambda: check_all(True)).pack(side="left")
        ttk.Button(left_actions, text="Uncheck All", command=lambda: check_all(False)).pack(side="left", padx=(8, 0))
        ttk.Button(left_actions, text="Rename Selected", command=apply_name).pack(side="left", padx=(18, 0))
        ttk.Button(left_actions, text="Open Preview", command=open_item_preview).pack(side="left", padx=(8, 0))
        ttk.Label(left_actions, text=f"Removed since last sync: {len(removed)}", style="Muted.TLabel").pack(side="left", padx=(18, 0))
        tk.Label(footer, textvariable=chosen_count_var, bg=Theme.PANEL_ALT, fg=Theme.FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(16, 0))
        ttk.Button(right_actions, text="Cancel", command=win.destroy).pack(side="right")

        def check_all(val: bool):
            for idx in range(len(order)):
                checked[idx].set(val)
                refresh_row(idx)
            update_details()
            update_selection_info()

        update_selection_info()
        self.root.wait_window(win)

    def _we_item_key(self, item: WallpaperItem) -> str:
        wid = str(getattr(item, 'workshop_id', '') or '').strip()
        if wid:
            return wid
        return str(Path(getattr(item, 'path', '')).resolve())

    def _persist_items(self):
        self.store.set_items(self.items, "items")
        self.store.set_items(self.we_items, "we_items")

    def _write_autostart(self):
        AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        if self.store.data.get("autostart"):
            content = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec=/usr/bin/mint-wallpaper-studio --autostart{" --minimized" if self.store.data.get("start_minimized_autostart", self.store.data.get("start_minimized", False)) else ""}
X-GNOME-Autostart-enabled=true
"""
            AUTOSTART_FILE.write_text(content, encoding="utf-8")
        else:
            AUTOSTART_FILE.unlink(missing_ok=True)



    def _force_kill_all_related_processes(self, include_self: bool = False):
        related = list(self._find_related_processes())
        current_pid = os.getpid()
        if include_self:
            related.append((current_pid, "current_app"))

        seen = set()
        targets = []
        for pid, args in related:
            if pid in seen:
                continue
            seen.add(pid)
            if pid == current_pid and not include_self:
                continue
            targets.append((pid, args))

        for pid, _args in targets:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

        time.sleep(0.8)

        for pid, _args in targets:
            try:
                os.kill(pid, 0)
            except Exception:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

        # extra safety net for helper processes
        extra_cmds = [
            ["pkill", "-f", "/opt/mint-wallpaper-studio"],
            ["pkill", "-f", "mint-wallpaper-studio"],
            ["pkill", "-f", "python3 main.py"],
            ["pkill", "-f", "python main.py"],
            ["pkill", "-f", "xwinwrap"],
            ["pkill", "-f", "mpv -wid"],
        ]
        if include_self:
            extra_cmds.insert(0, ["pkill", "-f", "mint-wallpaper-studio"])
        for cmd in extra_cmds:
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            except Exception:
                pass

        time.sleep(0.5)

    def _maybe_cleanup_stale_instances_on_start(self):
        related = self._find_related_processes()
        if not related:
            return
        lines = []
        for pid, args in related[:12]:
            pretty = args if len(args) < 180 else args[:177] + "..."
            lines.append(f"• {pid}: {pretty}")
        extra = "" if len(related) <= 12 else f"\n…and {len(related) - 12} more"
        msg = (
            "Mint Wallpaper Studio found other running or stale related processes.\n\n"
            "Do you want to stop them all before continuing?\n\n"
            + "\n".join(lines) + extra
        )
        if not self._ask_yes_no(APP_NAME, msg):
            return
        self._force_kill_all_related_processes(include_self=False)
        self.set_status("Cleaned up all older related processes before startup.")

    def _stop_related_processes(self, related=None, include_self: bool = False):
        related = list(related if related is not None else self._find_related_processes())
        current_pid = os.getpid()
        if include_self:
            related.append((current_pid, "current_app"))
        seen = set()
        deduped = []
        for pid, args in related:
            if pid in seen:
                continue
            seen.add(pid)
            deduped.append((pid, args))
        related = deduped
        for sig in (signal.SIGTERM, signal.SIGKILL):
            survivors = []
            for pid, args in related:
                if pid == current_pid and not include_self:
                    continue
                if self._terminate_pid(pid, sig):
                    continue
                survivors.append((pid, args))
            related = survivors
            if not related:
                break
            time.sleep(0.6)
        return related

    def _iter_process_lines(self):
        try:
            out = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            return []
        return [line.strip() for line in out.splitlines() if line.strip()]

    def _is_related_process_line(self, args: str) -> bool:
        a = f" {args.lower()} "
        # Do not flag the launcher shell itself just because the path contains
        # "mint_wallpaper_studio". We only want real app instances or the
        # wallpaper video helper processes.
        if "/run.sh" in a and (" bash " in a or " sh " in a):
            return False
        if (
            (" python" in a or " python3" in a or " python3.12" in a)
            and ("/main.py" in a or " main.py " in a or "/mws/app.py" in a)
        ):
            return True
        if " xwinwrap " in a and " mpv " in a and "--loop-file=inf" in a and "--no-input-default-bindings" in a:
            return True
        if " mpv " in a and " -wid " in a and "--loop-file=inf" in a and "--no-input-default-bindings" in a:
            return True
        return False

    def _find_related_processes(self):
        current_pid = os.getpid()
        related = []
        for line in self._iter_process_lines():
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
            except Exception:
                continue
            args = parts[1]
            if pid == current_pid:
                continue
            if self._is_related_process_line(args):
                related.append((pid, args))
        return related

    def _terminate_pid(self, pid: int, sig):
        try:
            os.kill(pid, sig)
            return True
        except Exception:
            return False

    def _hide_to_tray_from_specific_window(self, win):
        try:
            if win is not None and win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        if getattr(self, "options_window", None) is win:
            self.options_window = None
        self.hide_to_tray()

    def hide_to_tray(self):
        try:
            win = getattr(self, "options_window", None)
            if win is not None and win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        self.options_window = None
        if self._ensure_tray_icon():
            self.tray_minimized = True
            try:
                self.root.withdraw()
            except Exception:
                try:
                    self.root.iconify()
                except Exception:
                    pass
            self.set_status("App is still running in the tray. Use the applet near the clock to restore it.")
            self._set_tray_status("Tray active")
            if bool(self.store.data.get("tray_close_notice", True)):
                self._show_tray_notification(
                    "Mint Wallpaper Studio",
                    "Mint Wallpaper Studio is still running in the background. You can find its icon in the applets area near the clock.",
                )
            return
        try:
            self.root.iconify()
            self.set_status("App minimized. Restore it from the taskbar.")
        except Exception:
            pass

    def quit_all_instances(self, confirm: bool = True):
        if confirm and not self._ask_yes_no(APP_NAME, "Quit all Mint Wallpaper Studio instances and stop all related wallpaper/video processes?"):
            return

        try:
            self.close_to_tray_pref.set(False)
        except Exception:
            pass

        try:
            self.controller.stop_video()
            self._update_pause_button()
        except Exception:
            pass
        try:
            self._stop_preview_video()
        except Exception:
            pass
        try:
            self._close_preview_popup()
        except Exception:
            pass
        try:
            self._destroy_tray_icon()
        except Exception:
            pass

        self._force_kill_all_related_processes(include_self=False)

        self._shutdown = True
        try:
            if PRIMARY_PID_FILE.exists() and self._read_primary_pid() == os.getpid():
                PRIMARY_PID_FILE.unlink()
        except Exception:
            pass
        try:
            self._fullscreen_monitor_stop.set()
        except Exception:
            pass
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)


    def _set_tray_status(self, text: str):
        try:
            self.tray_status_var.set(text)
        except Exception:
            pass
        try:
            self.runtime_state_var.set(self._runtime_state_text())
        except Exception:
            pass

    def _create_tray_image(self):
        if Image is None:
            return None
        icon_path = Path(__file__).resolve().parent.parent / "lmws.png"
        try:
            if icon_path.exists():
                img = Image.open(icon_path).convert("RGBA")
                if img.size != (64, 64):
                    img = img.resize((64, 64))
                return img
        except Exception:
            pass

        img = Image.new("RGBA", (64, 64), (8, 17, 31, 255))
        if ImageDraw is not None:
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(13, 27, 48, 255), outline=(105, 167, 255, 255), width=2)
            draw.rectangle((19, 17, 28, 47), fill=(105, 167, 255, 255))
            draw.rectangle((36, 17, 45, 47), fill=(138, 240, 181, 255))
        return img

    def _tray_menu(self):
        if pystray is None:
            return None
        paused = bool(self.controller.is_video_running() and self.controller.video_paused)
        pause_text = "Resume Wallpaper" if paused else "Pause Wallpaper"
        mute_text = "Unmute Wallpaper" if bool(self.store.data.get("video_mute", True)) else "Mute Wallpaper"
        status_text = self._runtime_state_text().replace("Status: ", "Current Status: ")
        now_playing_text = self._now_playing_text()
        html_running = getattr(self.controller, "is_html_running", lambda: False)()

        def schedule(func, *args):
            return lambda icon=None, item=None: self.root.after(0, lambda: func(*args))

        return pystray.Menu(
            pystray.MenuItem(status_text, lambda icon=None, item=None: None, enabled=False),
            pystray.MenuItem(now_playing_text, lambda icon=None, item=None: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Mint Wallpaper Studio", schedule(self._show_from_tray), default=True),
            pystray.MenuItem("Peek Desktop", schedule(self._peek_desktop_temporarily)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(pause_text if not html_running else "Pause unavailable for HTML", schedule(self.toggle_wallpaper_pause), enabled=lambda item: self.controller.is_video_running() and not self.wallpaper_paused_by_fullscreen and not html_running),
            pystray.MenuItem(mute_text, schedule(self.toggle_tray_mute)),
            pystray.MenuItem("Volume...", schedule(self.show_tray_volume_window)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Random Now", schedule(self.apply_random)),
            pystray.MenuItem("Next Wallpaper", schedule(self.apply_random)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Options", schedule(self.show_options)),
            pystray.MenuItem("Hide to Tray Now", schedule(self.hide_to_tray)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", schedule(lambda: self.quit_all_instances(confirm=False))),
        )

    def _schedule_on_ui(self, func, *args):
        try:
            self.root.after(0, lambda: func(*args))
        except Exception:
            pass

    def _apply_audio_settings(self, volume: int | None = None, mute: bool | None = None, save: bool = True, reapply: bool = True):
        current_volume = int(self.store.data.get("video_volume", 35))
        current_mute = bool(self.store.data.get("video_mute", True))

        if volume is None:
            volume = current_volume
        if mute is None:
            mute = current_mute

        try:
            volume = int(volume)
        except Exception:
            volume = current_volume

        volume = max(0, min(100, volume))
        mute = bool(mute)

        changed = (
            volume != int(self.store.data.get("video_volume", 35)) or
            mute != bool(self.store.data.get("video_mute", True))
        )

        self.store.data["video_volume"] = volume
        self.store.data["video_mute"] = mute
        self.controller.set_audio_options(volume, mute)

        if changed and reapply:
            try:
                self.controller.apply_audio_live()
            except Exception:
                pass

        if save:
            self.store.save()

        mode = "muted" if mute else f"volume {volume}%"
        self.set_status(f"Video audio set to {mode}.")
        if not getattr(self, "tray_volume_win", None):
            self._update_tray_menu()

    def _queue_audio_reapply(self, delay_ms: int = 220):
        try:
            pending = getattr(self, "_audio_reapply_after_id", None)
            if pending:
                self.root.after_cancel(pending)
        except Exception:
            pass

        def run():
            self._audio_reapply_after_id = None
            try:
                self.controller.reapply_current_video_with_audio()
            except Exception:
                pass

        try:
            self._audio_reapply_after_id = self.root.after(delay_ms, run)
        except Exception:
            run()

    def _flush_audio_reapply(self):
        try:
            pending = getattr(self, "_audio_reapply_after_id", None)
            if pending:
                self.root.after_cancel(pending)
                self._audio_reapply_after_id = None
        except Exception:
            pass
        try:
            self.controller.reapply_current_video_with_audio()
        except Exception:
            pass

    def set_tray_mute(self, mute: bool):
        self._apply_audio_settings(mute=bool(mute))

    def toggle_tray_mute(self):
        self.set_tray_mute(not bool(self.store.data.get("video_mute", True)))

    def set_tray_volume(self, volume: int, save: bool = True):
        self._apply_audio_settings(volume=volume, mute=False, save=save)

    def adjust_tray_volume(self, delta: int):
        base = int(self.store.data.get("video_volume", 35))
        self.set_tray_volume(max(0, min(100, base + int(delta))))

    def _save_audio_only(self):
        try:
            self.store.save()
        except Exception:
            pass

    def _close_tray_volume_window(self):
        win = getattr(self, "tray_volume_win", None)
        self.tray_volume_win = None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass

    def show_tray_volume_window(self):
        existing = getattr(self, "tray_volume_win", None)
        if existing is not None:
            try:
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return
            except Exception:
                self.tray_volume_win = None

        root_visible = False
        try:
            root_visible = bool(int(self.root.winfo_viewable())) and str(self.root.state()) != "withdrawn"
        except Exception:
            root_visible = False

        win = tk.Toplevel(self.root)
        self.tray_volume_win = win
        win.withdraw()
        win.title("Wallpaper Audio")
        win.configure(bg=Theme.BG)
        try:
            win.resizable(False, False)
        except Exception:
            pass
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        if root_visible:
            try:
                win.transient(self.root)
            except Exception:
                pass
        try:
            win.minsize(440, 230)
        except Exception:
            pass
        width = 440
        height = 230
        try:
            if root_visible:
                rx = self.root.winfo_rootx()
                ry = self.root.winfo_rooty()
                rw = max(width, self.root.winfo_width())
                x = rx + max(20, rw - width - 20)
                y = ry + 80
            else:
                sw = max(width + 40, win.winfo_screenwidth())
                sh = max(height + 80, win.winfo_screenheight())
                x = max(30, sw - width - 90)
                y = max(30, sh - height - 120)
            win.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            win.geometry(f"{width}x{height}")

        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Wallpaper audio", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Adjust the live volume for video wallpapers even while the app is hidden in the tray.",
            style="Muted.TLabel",
            wraplength=390,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        volume_var = tk.IntVar(value=int(self.store.data.get("video_volume", 35)))
        mute_var = tk.BooleanVar(value=bool(self.store.data.get("video_mute", True)))
        value_var = tk.StringVar(value=f"{volume_var.get()}%")

        row = ttk.Frame(frame)
        row.pack(fill="x")
        scale = ttk.Scale(row, from_=0, to=100, orient="horizontal")
        scale.pack(side="left", fill="x", expand=True)
        ttk.Label(row, textvariable=value_var, width=5, anchor="e", style="Muted.TLabel").pack(side="left", padx=(10, 0))
        scale.set(volume_var.get())

        def apply_from_scale(_evt=None):
            value = int(round(float(scale.get())))
            volume_var.set(value)
            value_var.set(f"{value}%")
            self._apply_audio_settings(volume=value, mute=bool(mute_var.get()), save=False, reapply=True)

        scale.configure(command=lambda _=None: apply_from_scale())

        mute_btn = ttk.Checkbutton(frame, text="Mute wallpaper audio", variable=mute_var)
        mute_btn.pack(anchor="w", pady=(12, 8))

        def on_mute_changed(*_):
            muted = bool(mute_var.get())
            self._apply_audio_settings(volume=int(volume_var.get()), mute=muted, save=False, reapply=True)

        mute_var.trace_add("write", on_mute_changed)

        quick = ttk.Frame(frame)
        quick.pack(fill="x", pady=(2, 0))
        for idx, lvl in enumerate((0, 25, 50, 75, 100)):
            ttk.Button(quick, text=f"{lvl}%", command=lambda v=lvl: (scale.set(v), apply_from_scale())).grid(row=0, column=idx, padx=(0 if idx == 0 else 6, 0), sticky="ew")
            quick.columnconfigure(idx, weight=1)

        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(14, 0))

        def finish_and_close():
            self._save_audio_only()
            self._update_tray_menu()
            self._close_tray_volume_window()

        ttk.Button(actions, text="Close", command=finish_and_close).pack(side="right")
        ttk.Button(actions, text="Save", command=finish_and_close).pack(side="right", padx=(0, 8))

        def on_close():
            self._flush_audio_reapply()
            self._save_audio_only()
            self._update_tray_menu()
            self._close_tray_volume_window()

        win.protocol("WM_DELETE_WINDOW", on_close)
        try:
            win.deiconify()
            win.lift()
            win.focus_force()
        except Exception:
            pass


    
    
    def _open_html_debug_window(self):
        item = self.primary_item()
        if not item or item.media_type != "html":
            self._show_info("HTML Debug", "Select an HTML item first.")
            return

        html_path = Path(item.path)
        if not html_path.exists():
            self._show_error("HTML Debug", "HTML file not found.")
            return

        win = tk.Toplevel(self.root)
        self._style_toplevel(win, title="HTML Debug", geometry="1100x780", modal=False)
        try:
            win.minsize(920, 660)
        except Exception:
            pass

        wrap = ttk.Frame(win, style="Card.TFrame", padding=12)
        wrap.pack(fill="both", expand=True, padx=12, pady=12)

        top = ttk.Frame(wrap, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="HTML Renderer Test", style="Title.TLabel").pack(side="left")

        info_var = tk.StringVar(value="Ready.")

        def refresh_log():
            log_file = Path("/tmp/mint_wallpaper_studio_html.log")
            log_text.configure(state="normal")
            log_text.delete("1.0", "end")
            if log_file.exists():
                try:
                    log_text.insert("1.0", log_file.read_text(encoding="utf-8", errors="replace"))
                    info_var.set(f"Showing log: {log_file}")
                except Exception as exc:
                    log_text.insert("1.0", f"Could not read log: {exc}")
                    info_var.set("Could not read HTML log.")
            else:
                log_text.insert("1.0", "No HTML debug log found yet.")
                info_var.set("No HTML debug log found yet.")
            log_text.configure(state="disabled")

        def open_internal_test():
            try:
                runner = Path(__file__).resolve().parent / "html_test_window.py"
                import subprocess
                subprocess.Popen(["python3", str(runner), str(html_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                info_var.set(f"Opened internal renderer test: {html_path.name}")
            except Exception as exc:
                info_var.set(f"Could not open internal renderer test: {exc}")

        def open_html():
            try:
                import webbrowser
                webbrowser.open(f"file://{html_path}")
                info_var.set(f"Opened in browser: {html_path}")
            except Exception as exc:
                info_var.set(f"Could not open browser: {exc}")

        ttk.Button(top, text="Refresh Log", command=refresh_log).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="Open HTML", command=open_html).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="Open Internal Test", command=open_internal_test).pack(side="right")

        ttk.Label(
            wrap,
            text="Open Internal Test uses the same internal WebKit renderer as HTML wallpaper mode, but in a normal window. If it is visible there, the problem is the wallpaper embedding. If it is black there too, the renderer path is the issue.",
            style="Subtle.TLabel",
            wraplength=950,
            justify="left",
        ).pack(fill="x", pady=(8, 10))

        info_label = tk.Label(
            wrap,
            textvariable=info_var,
            bg="#07111f",
            fg="#d7e7ff",
            anchor="center",
            justify="center",
            padx=12,
            pady=18,
        )
        info_label.pack(fill="x")

        ttk.Label(wrap, text="Debug log", style="Body.TLabel").pack(anchor="w", pady=(12, 6))
        log_text = tk.Text(
            wrap,
            height=24,
            wrap="word",
            bg="#07111f",
            fg="#d7e7ff",
            insertbackground="#d7e7ff",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
        )
        log_text.pack(fill="both", expand=True)

        refresh_log()

    def _show_tray_notification(self, title: str, message: str):
        try:
            subprocess.Popen(["notify-send", title, message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _build_appindicator_menu(self):
        if Gtk is None:
            return None
        menu = Gtk.Menu()

        def add_item(label, callback, sensitive=True):
            item = Gtk.MenuItem(label=label)
            item.set_sensitive(bool(sensitive))
            item.connect("activate", lambda *_: self._schedule_on_ui(callback))
            menu.append(item)
            return item

        self.tray_status_item = Gtk.MenuItem(label=self._runtime_state_text().replace("Status: ", "Current Status: "))
        self.tray_status_item.set_sensitive(False)
        menu.append(self.tray_status_item)
        self.tray_now_playing_item = Gtk.MenuItem(label=self._now_playing_text())
        self.tray_now_playing_item.set_sensitive(False)
        menu.append(self.tray_now_playing_item)
        menu.append(Gtk.SeparatorMenuItem())
        add_item("Show Mint Wallpaper Studio", self._show_from_tray)
        add_item("Peek Desktop", self._peek_desktop_temporarily)
        menu.append(Gtk.SeparatorMenuItem())
        pause_label = "Pause unavailable for HTML" if getattr(self.controller, "is_html_running", lambda: False)() else "Pause Wallpaper"
        self.tray_pause_item = add_item(pause_label, self.toggle_wallpaper_pause, sensitive=(not getattr(self.controller, "is_html_running", lambda: False)()))
        self.tray_mute_item = add_item("Mute Wallpaper", self.toggle_tray_mute)
        add_item("Volume...", self.show_tray_volume_window)
        menu.append(Gtk.SeparatorMenuItem())
        add_item("Random Now", self.apply_random)
        add_item("Next Wallpaper", self.apply_random)
        menu.append(Gtk.SeparatorMenuItem())
        add_item("Open Options", self.show_options)
        add_item("Hide to Tray Now", self.hide_to_tray)
        menu.append(Gtk.SeparatorMenuItem())
        add_item("Quit", lambda: self.quit_all_instances(confirm=False))
        try:
            for sig in ("show", "map", "popped-up", "notify::visible"):
                try:
                    menu.connect(sig, lambda *_: self._schedule_on_ui(self._tray_menu_peek_begin))
                except Exception:
                    pass
            for sig in ("hide", "unmap", "deactivate", "selection-done"):
                try:
                    menu.connect(sig, lambda *_: self._schedule_on_ui(self._tray_menu_peek_end))
                except Exception:
                    pass
        except Exception:
            pass
        menu.show_all()
        self.tray_menu_widget = menu
        self._refresh_appindicator_menu_labels()
        return menu

    def _refresh_appindicator_menu_labels(self):
        if Gtk is None:
            return
        try:
            paused = bool(self.controller.is_video_running() and self.controller.video_paused)
            pause_text = "Resume Wallpaper" if paused else "Pause Wallpaper"
            mute_text = "Unmute Wallpaper" if bool(self.store.data.get("video_mute", True)) else "Mute Wallpaper"
            pause_sensitive = self.controller.is_video_running() and not self.wallpaper_paused_by_fullscreen
            if self.tray_status_item is not None:
                self.tray_status_item.set_label(self._runtime_state_text().replace("Status: ", "Current Status: "))
            if self.tray_now_playing_item is not None:
                self.tray_now_playing_item.set_label(self._now_playing_text())
            if self.tray_pause_item is not None:
                self.tray_pause_item.set_label(pause_text)
                self.tray_pause_item.set_sensitive(bool(pause_sensitive))
            if self.tray_mute_item is not None:
                self.tray_mute_item.set_label(mute_text)
        except Exception:
            pass

    def _run_gtk_loop(self):
        if Gtk is None:
            return
        try:
            Gtk.main()
        except Exception:
            pass

    def _ensure_gtk_loop(self):
        if Gtk is None:
            return False
        thread = getattr(self, "gtk_loop_thread", None)
        if thread is not None and thread.is_alive():
            return True
        self.gtk_loop_thread = threading.Thread(target=self._run_gtk_loop, daemon=True)
        self.gtk_loop_thread.start()
        return True

    def _create_appindicator(self):
        if AppIndicator3 is None or Gtk is None:
            return False
        self._ensure_gtk_loop()
        icon_path = str((Path(__file__).resolve().parent.parent / "lmws.png").resolve())

        def build():
            try:
                indicator = AppIndicator3.Indicator.new(
                    "mint-wallpaper-studio",
                    icon_path,
                    AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
                )
                try:
                    indicator.set_icon_full(icon_path, APP_NAME)
                except Exception:
                    pass
                indicator.set_title(APP_NAME)
                indicator.set_menu(self._build_appindicator_menu())
                indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
                self.tray_indicator = indicator
                self._set_tray_status("Tray active")
            except Exception as exc:
                self.tray_indicator = None
                self._set_tray_status(f"Tray unavailable: {exc}")

        try:
            GLib.idle_add(build)
            return True
        except Exception:
            return False

    def _ensure_tray_icon(self):
        if not self.tray_enabled:
            self._set_tray_status("Tray unavailable")
            return False
        if self.tray_backend == "appindicator":
            if self.tray_indicator is not None:
                return True
            return self._create_appindicator()
        if self.tray_icon is not None:
            return True
        try:
            icon_image = self._create_tray_image()
            self.tray_icon = pystray.Icon("mint-wallpaper-studio", icon=icon_image, title="Mint Wallpaper Studio", menu=self._tray_menu())
            self.tray_thread = threading.Thread(target=self._run_tray_icon, daemon=True)
            self.tray_thread.start()
            self._set_tray_status("Tray active")
            return True
        except Exception as exc:
            self.tray_icon = None
            self._set_tray_status(f"Tray unavailable: {exc}")
            return False

    def _run_tray_icon(self):
        icon = self.tray_icon
        if icon is None:
            return
        try:
            icon.run()
        except Exception:
            pass

    def _update_tray_menu(self):
        if self.tray_backend == "appindicator":
            indicator = self.tray_indicator
            if indicator is None or GLib is None:
                return
            def refresh_only():
                try:
                    if self.tray_menu_widget is None:
                        indicator.set_menu(self._build_appindicator_menu())
                    else:
                        self._refresh_appindicator_menu_labels()
                except Exception:
                    pass
                return False
            try:
                GLib.idle_add(refresh_only)
            except Exception:
                pass
            return
        icon = self.tray_icon
        if icon is None:
            return
        try:
            icon.menu = self._tray_menu()
            icon.update_menu()
        except Exception:
            pass

    def _destroy_tray_icon(self):
        if self.tray_backend == "appindicator":
            indicator = self.tray_indicator
            self.tray_indicator = None
            self.tray_menu_widget = None
            self.tray_status_item = None
            self.tray_now_playing_item = None
            self.tray_pause_item = None
            self.tray_mute_item = None
            if indicator is not None and GLib is not None:
                def hide_indicator():
                    try:
                        indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
                    except Exception:
                        pass
                    return False
                try:
                    GLib.idle_add(hide_indicator)
                except Exception:
                    pass
            self._set_tray_status("Tray stopped")
            return
        icon = self.tray_icon
        self.tray_icon = None
        self.tray_thread = None
        if icon is None:
            return
        try:
            icon.stop()
        except Exception:
            pass
        self._set_tray_status("Tray stopped")

    def _show_from_tray(self):
        self.tray_minimized = False
        self.tray_volume_win = None
        try:
            self.root.deiconify()
            self.root.withdraw()
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass
        self.set_status("Restored from tray.")
        self._set_tray_status("Tray active")

    def _quit_from_tray(self):
        self.quit_all_instances()

    def show_options(self):
        self._show_from_tray()
        try:
            self.open_options()
        except Exception:
            pass

    def _stop_preview_video(self):
        proc = getattr(self, "preview_video_proc", None)
        self.preview_video_proc = None
        if proc and getattr(proc, "poll", lambda: 0)() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def on_close(self):
        try:
            if bool(getattr(self, "close_to_tray_pref", None).get() if getattr(self, "close_to_tray_pref", None) is not None else True):
                self.hide_to_tray()
                return
        except Exception:
            pass
        self._shutdown = True
        try:
            if PRIMARY_PID_FILE.exists() and self._read_primary_pid() == os.getpid():
                PRIMARY_PID_FILE.unlink()
        except Exception:
            pass
        try:
            self._fullscreen_monitor_stop.set()
        except Exception:
            pass
        if self._blink_job:
            try:
                self.root.after_cancel(self._blink_job)
            except Exception:
                pass
            self._blink_job = None
        self.store.data["window_geometry"] = self.root.geometry()
        self.store.data["active_tab"] = self.tab_var.get()
        self.store.data["sort_mode"] = self.sort_var.get()
        self.store.data["show_unsupported_we"] = self.show_unsupported_we.get()
        self.store.data["monitor_sync_mode"] = self.monitor_sync_mode.get()
        self.store.data["playlist_target"] = self.playlist_target.get()
        self.store.data["preview_autoplay_video"] = self.preview_autoplay_video.get()
        self.store.data["start_minimized_launch"] = self.start_minimized_launch_pref.get()
        self.store.data["start_minimized_autostart"] = self.start_minimized_autostart_pref.get()
        self.store.data["start_minimized"] = bool(self.start_minimized_launch_pref.get() or self.start_minimized_autostart_pref.get())
        self._persist_items()
        self.store.save()
        self._close_preview_popup()
        self._stop_preview_video()
        self.controller.stop_video()
        self._update_pause_button()
        self._destroy_tray_icon()
        if self.preview_tmp:
            try:
                Path(self.preview_tmp).unlink(missing_ok=True)
            except Exception:
                pass
        self.root.destroy()
