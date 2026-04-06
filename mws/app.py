from __future__ import annotations
import os
import signal
import random
import shutil
import time
import tempfile
import subprocess
import threading
import hashlib
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
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

from .config import APP_NAME, AUTOSTART_DIR, AUTOSTART_FILE, ConfigStore, INTERNAL_LIBRARY_DIR, PREVIEW_CACHE_DIR
from .controller import WallpaperController
from .models import WallpaperItem
from .preview import PIL_AVAILABLE, image_resolution, render_image_preview, render_video_thumbnail, render_image_preview_file, render_video_thumbnail_file, find_html_preview_image
from .utils import classify_media, human_dt, human_size, open_in_file_manager, probe_resolution, scan_paths, list_monitors, command_exists, session_is_x11
from .we_sync import sync_wallpaper_engine, detect_steam_install_type




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

        self.items: List[WallpaperItem] = self.store.get_items("items")
        self.we_items: List[WallpaperItem] = self.store.get_items("we_items")
        self.filtered: List[WallpaperItem] = []
        self.preview_image = None
        self.preview_tmp = None
        self.random_job = None
        self._blink_on = True
        self._blink_job = None
        self.auto_mode_var = tk.StringVar(value=str(self.store.data.get("auto_change_mode", "off")))
        self.auto_interval_var = tk.IntVar(value=int(self.store.data.get("random_interval_minutes", 10)))

        self.search_var = tk.StringVar()
        self.sort_var = tk.StringVar(value=self._norm(self.store.data.get("sort_mode"), self.SORTS, "name_asc"))
        self.tab_var = tk.StringVar(value=self._norm(self.store.data.get("active_tab"), dict(self.TABS), "all"))
        self.status_var = tk.StringVar(value="Ready")
        self.count_var = tk.StringVar(value="0 items")
        self.preview_enabled = tk.BooleanVar(value=bool(self.store.data.get("preview_visible", True)))
        self.show_unsupported_we = tk.BooleanVar(value=bool(self.store.data.get("show_unsupported_we", False)))
        self.monitor_sync_mode = tk.BooleanVar(value=bool(self.store.data.get("monitor_sync_mode", True)))
        self.playlist_target = tk.StringVar(value=str(self.store.data.get("playlist_target", "synced")))
        self.preview_autoplay_video = tk.BooleanVar(value=bool(self.store.data.get("preview_autoplay_video", True)))
        launch_min_pref = self.store.data.get("start_minimized_launch", self.store.data.get("start_minimized", False))
        autostart_min_pref = self.store.data.get("start_minimized_autostart", self.store.data.get("start_minimized", False))
        self.start_minimized_launch_pref = tk.BooleanVar(value=bool(launch_min_pref))
        self.start_minimized_autostart_pref = tk.BooleanVar(value=bool(autostart_min_pref))
        self.close_to_tray_pref = tk.BooleanVar(value=bool(self.store.data.get("close_to_tray", True)))
        self.pause_on_fullscreen_pref = tk.BooleanVar(value=bool(self.store.data.get("pause_on_fullscreen", True)))
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
        self.start_minimized_arg = bool(start_minimized)
        self.launched_from_autostart = bool(launched_from_autostart)

        self._repair_items()
        self._style()
        self._build()
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
        self._start_random_if_enabled()
        self.root.after(1200, self._fullscreen_pause_tick)

    def _repair_items(self):
        changed = False
        for seq in (self.items, self.we_items):
            for item in seq:
                if not hasattr(item, "enabled"):
                    item.enabled = True
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

    def _dark_messagebox(self, title: str, message: str, kind: str = "info", buttons=("OK",), default=None):
        result = {"value": None}
        win = tk.Toplevel(self.root)
        self.options_window = win
        self._style_toplevel(win, title=title, modal=True)
        try:
            win.resizable(False, False)
        except Exception:
            pass

        outer = ttk.Frame(win, style="Card.TFrame", padding=14)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer, style="Card.TFrame")
        top.pack(fill="both", expand=True)

        icons = {"info": "ℹ", "warning": "⚠", "error": "✖", "question": "?"}
        icon_wrap = tk.Frame(top, bg=Theme.PANEL_ALT, highlightbackground=Theme.BORDER, highlightthickness=1)
        icon_wrap.pack(side="left", padx=(0, 12), pady=(2, 0), anchor="n")
        tk.Label(icon_wrap, text=icons.get(kind, "ℹ"), bg=Theme.PANEL_ALT, fg=Theme.ACCENT, font=("Segoe UI", 20, "bold"), width=2).pack(padx=8, pady=6)

        text_wrap = ttk.Frame(top, style="Card.TFrame")
        text_wrap.pack(side="left", fill="both", expand=True)
        ttk.Label(text_wrap, text=title, style="TitlePopup.TLabel").pack(anchor="w")
        tk.Label(
            text_wrap, text=message, bg=Theme.PANEL, fg=Theme.FG,
            justify="left", anchor="w", wraplength=520, font=("Segoe UI", 11)
        ).pack(anchor="w", fill="both", expand=True, pady=(8, 0))

        btn_row = ttk.Frame(outer, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(14, 0))

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
            ttk.Button(btn_row, text=label, style=style, command=lambda v=label: choose(v)).pack(side="right", padx=(8, 0))

        win.bind("<Escape>", lambda e: choose(None))
        win.protocol("WM_DELETE_WINDOW", lambda: choose(None))
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
            self._style_toplevel(dlg, title=title, geometry="760x420")
            dlg.resizable(False, False)

            frame = ttk.Frame(dlg, padding=18)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text=title, style="Title.TLabel").pack(anchor="w")
            ttk.Label(frame, text=message, style="PanelBody.TLabel", wraplength=680, justify="left").pack(anchor="w", pady=(12, 0))

            result = {"value": False}
            btns = ttk.Frame(frame)
            btns.pack(fill="x", pady=(28, 0))
            ttk.Button(btns, text="No", command=lambda: (result.__setitem__("value", False), dlg.destroy())).pack(side="right")
            ttk.Button(btns, text="Yes", style="Accent.TButton", command=lambda: (result.__setitem__("value", True), dlg.destroy())).pack(side="right", padx=(0, 10), ipadx=10, ipady=3)

            dlg.update_idletasks()
            try:
                px = parent.winfo_rootx()
                py = parent.winfo_rooty()
                pw = parent.winfo_width()
                ph = parent.winfo_height()
                dw = dlg.winfo_width()
                dh = dlg.winfo_height()
                x = px + max(0, (pw - dw) // 2)
                y = py + max(0, (ph - dh) // 2)
                dlg.geometry(f"+{x}+{y}")
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
        self._style_toplevel(win, title=title, modal=True)
        try:
            win.resizable(False, False)
        except Exception:
            pass

        outer = ttk.Frame(win, style="Card.TFrame", padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=title, style="TitlePopup.TLabel").pack(anchor="w")
        tk.Label(
            outer, text=prompt, bg=Theme.PANEL, fg=Theme.FG,
            justify="left", anchor="w", wraplength=520, font=("Segoe UI", 11)
        ).pack(anchor="w", fill="x", pady=(8, 8))

        value = tk.StringVar(value=initialvalue)
        entry = ttk.Entry(outer, textvariable=value, width=48)
        entry.pack(fill="x")
        entry.focus_set()
        entry.select_range(0, "end")

        btn_row = ttk.Frame(outer, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(14, 0))

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
        header.pack(fill="x", pady=(0, 8))

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

        auto_row = tk.Frame(left, bg=Theme.PANEL_ALT, highlightbackground=Theme.ACCENT, highlightthickness=1, bd=0)
        auto_row.pack(fill="x", pady=(0, 10))
        tk.Label(auto_row, text="Auto change", bg=Theme.PANEL_ALT, fg=Theme.FG, font=("Segoe UI", 11, "bold")).pack(side="left", padx=(12, 10), pady=8)
        for value, label in (("off", "Off"), ("playlist", "Playlist"), ("random", "Random")):
            ttk.Radiobutton(auto_row, text=label, value=value, variable=self.auto_mode_var, command=self._auto_controls_changed).pack(side="left", padx=(6, 0), pady=6)
        tk.Label(auto_row, text="Every", bg=Theme.PANEL_ALT, fg=Theme.FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(16, 4), pady=8)
        self.auto_interval_spin = ttk.Spinbox(auto_row, from_=1, to=1440, textvariable=self.auto_interval_var, width=6, command=self._auto_controls_changed)
        self.auto_interval_spin.pack(side="left", pady=6)
        self.auto_interval_spin.bind("<KeyRelease>", lambda e: self._auto_controls_changed())
        tk.Label(auto_row, text="min", bg=Theme.PANEL_ALT, fg=Theme.FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(6, 12), pady=8)
        self.auto_hint_var = tk.StringVar(value="")
        tk.Label(auto_row, textvariable=self.auto_hint_var, bg=Theme.PANEL_ALT, fg=Theme.MUTED, font=("Segoe UI", 10, "bold")).pack(side="right", padx=(12, 12), pady=8)

        actionbar = ttk.Frame(left)
        actionbar.pack(fill="x", pady=(0, 6))
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
        ttk.Label(searchbar, text="Search", style="Body.TLabel").pack(side="left")
        search = ttk.Entry(searchbar, textvariable=self.search_var, width=42)
        search.pack(side="left", fill="x", expand=True, padx=(8, 10))

        tk.Label(searchbar, text="Playlist Target", bg=Theme.BG, fg=Theme.FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.target_box = ttk.Combobox(searchbar, state="readonly", width=22)
        self.target_box.pack(side="left", padx=(0, 10))
        self.target_box.bind("<<ComboboxSelected>>", lambda e: self._target_changed())

        ttk.Checkbutton(searchbar, text="Sync monitors", variable=self.monitor_sync_mode, command=self._sync_mode_changed).pack(side="left")

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

    def _refresh_target_box(self):
        names = self._selected_monitor_names()
        values = ["synced"] + names
        labels = [self._friendly_target_label(v) for v in values]
        if hasattr(self, "target_box"):
            self._target_value_map = dict(zip(labels, values))
            self.target_box["values"] = labels
            cur = self.playlist_target.get() or "synced"
            if cur not in values:
                cur = "synced"
                self.playlist_target.set(cur)
                self.store.data["playlist_target"] = cur
                self.store.save()
            self.target_box.set(self._friendly_target_label(cur))
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
        mode = "shared" if self.monitor_sync_mode.get() else "per-monitor"
        if hasattr(self, "monitor_info_var"):
            self.monitor_info_var.set(", ".join(names) + f"  •  mode: {mode}")

    def _sync_mode_changed(self):
        self.store.data["monitor_sync_mode"] = self.monitor_sync_mode.get()
        self.store.save()
        self._update_monitor_info()
        self.refresh_list()
        self.set_status("Monitor sync mode updated")

    def _friendly_target_label(self, target: str) -> str:
        return "All playlist" if target == "synced" else target

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


    def _update_auto_change_hint(self):
        if not hasattr(self, "auto_hint_var"):
            return
        mode = self.auto_mode_var.get()
        if mode == "playlist":
            self.auto_hint_var.set("Playlist mode uses the All playlist")
        elif mode == "random":
            self.auto_hint_var.set("Random mode picks from enabled items")
        else:
            self.auto_hint_var.set("")

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
        self.store.save()
        self._refresh_tab_buttons()
        self.refresh_list()

    def _find_item_by_id(self, item_id: str):
        for item in self.all_items():
            if getattr(item, "id", "") == item_id:
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
            if not self.monitor_sync_mode.get() and self.playlist_target.get() not in {"", "synced"} and item.media_type == "image":
                self.controller.set_image_multi({self.playlist_target.get(): item.path})
            else:
                self.controller.apply(item)
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
            self.clear_preview("Unsupported Wallpaper Engine item\nScene/Web wallpapers are listed but not directly playable yet.")
            return
        p = Path(item.path)
        if not p.exists():
            self.clear_preview("File not found")
            return

        self._close_preview_popup()
        self.preview_click_path = str(p) if item.media_type in {'video','html','image'} else None
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

    def _has_fullscreen_window_x11(self):
        if not session_is_x11() or not command_exists("xprop"):
            return False
        try:
            current_desktop = None
            desktop_res = subprocess.run(
                ["xprop", "-root", "_NET_CURRENT_DESKTOP"],
                capture_output=True, text=True, check=False
            )
            desktop_text = (desktop_res.stdout or "") + "\n" + (desktop_res.stderr or "")
            desktop_match = re.search(r"=\s*(\d+)", desktop_text)
            if desktop_match:
                current_desktop = int(desktop_match.group(1))

            screen_w = None
            screen_h = None
            if command_exists("xwininfo"):
                root_info = subprocess.run(
                    ["xwininfo", "-root"],
                    capture_output=True, text=True, check=False
                )
                root_text = (root_info.stdout or "") + "\n" + (root_info.stderr or "")
                w_match = re.search(r"Width:\s*(\d+)", root_text)
                h_match = re.search(r"Height:\s*(\d+)", root_text)
                if w_match and h_match:
                    screen_w = int(w_match.group(1))
                    screen_h = int(h_match.group(1))

            root_id = None
            try:
                root_id = hex(int(self.root.winfo_id())).lower()
            except Exception:
                root_id = None

            if command_exists("wmctrl"):
                wmctrl_res = subprocess.run(
                    ["wmctrl", "-lG"],
                    capture_output=True, text=True, check=False
                )
                for line in (wmctrl_res.stdout or "").splitlines():
                    parts = line.split(None, 7)
                    if len(parts) < 7:
                        continue
                    win_id = parts[0].lower()
                    if win_id == "0x0" or (root_id and win_id == root_id):
                        continue
                    try:
                        desktop = int(parts[1])
                        x = int(parts[2])
                        y = int(parts[3])
                        w = int(parts[4])
                        h = int(parts[5])
                    except Exception:
                        continue
                    if current_desktop is not None and desktop not in (-1, current_desktop):
                        continue
                    name_res = subprocess.run(
                        ["xprop", "-id", win_id, "WM_CLASS", "_NET_WM_STATE"],
                        capture_output=True, text=True, check=False
                    )
                    props = ((name_res.stdout or "") + "\n" + (name_res.stderr or "")).lower()
                    if "mint-wallpaper-studio" in props:
                        continue
                    if "_net_wm_state_hidden" in props:
                        continue
                    if "_net_wm_state_fullscreen" in props:
                        return True
                    if (
                        screen_w and screen_h
                        and w >= max(200, screen_w - 24)
                        and h >= max(150, screen_h - 80)
                        and x <= 12
                        and y <= 48
                    ):
                        return True

            root_res = subprocess.run(
                ["xprop", "-root", "_NET_CLIENT_LIST_STACKING"],
                capture_output=True, text=True, check=False
            )
            line = (root_res.stdout or "") + "\n" + (root_res.stderr or "")
            win_ids = re.findall(r"0x[0-9a-fA-F]+", line)
            if not win_ids:
                fallback_res = subprocess.run(
                    ["xprop", "-root", "_NET_CLIENT_LIST"],
                    capture_output=True, text=True, check=False
                )
                line = (fallback_res.stdout or "") + "\n" + (fallback_res.stderr or "")
                win_ids = re.findall(r"0x[0-9a-fA-F]+", line)
            for win_id in reversed(win_ids):
                win_key = win_id.lower()
                if win_key == "0x0" or (root_id and win_key == root_id):
                    continue
                prop_res = subprocess.run(
                    ["xprop", "-id", win_id, "WM_CLASS", "_NET_WM_STATE", "_NET_WM_DESKTOP"],
                    capture_output=True, text=True, check=False
                )
                props = ((prop_res.stdout or "") + "\n" + (prop_res.stderr or "")).lower()
                if "mint-wallpaper-studio" in props:
                    continue
                if "_net_wm_state_hidden" in props:
                    continue
                if current_desktop is not None:
                    desk_match = re.search(r"_net_wm_desktop\(cardinal\) = (\d+)", props)
                    if desk_match and int(desk_match.group(1)) not in (-1, current_desktop):
                        continue
                if "_net_wm_state_fullscreen" in props:
                    return True
            return False
        except Exception:
            return False

    def _fullscreen_pause_tick(self):
        if getattr(self, "_shutdown", False):
            return
        try:
            active_video = self.controller.is_video_running()
            auto_pause_enabled = bool(self.pause_on_fullscreen_pref.get())
            fullscreen_active = active_video and auto_pause_enabled and self._has_fullscreen_window_x11()

            if fullscreen_active and not self.controller.video_paused:
                if self.controller.pause_video():
                    self.wallpaper_paused_by_fullscreen = True
                    self.wallpaper_paused_by_user = False
                    self.set_status("Paused video wallpaper because a fullscreen window is active.")
            elif (
                active_video
                and self.controller.video_paused
                and self.wallpaper_paused_by_fullscreen
                and not fullscreen_active
            ):
                if self.controller.resume_video():
                    self.wallpaper_paused_by_fullscreen = False
                    self.set_status("Resumed video wallpaper after fullscreen window closed.")
            elif not active_video:
                self.wallpaper_paused_by_fullscreen = False
                self.wallpaper_paused_by_user = False
        except Exception:
            pass
        self._update_pause_button()
        try:
            self.root.after(1200, self._fullscreen_pause_tick)
        except Exception:
            pass

    def apply_selected(self):
        item = self.primary_item()
        if not item:
            self.set_status("No item selected")
            return
        if not item.supported:
            self._show_info(APP_NAME, "This Wallpaper Engine item is preview-only right now. Scene/Application entries cannot be applied yet.")
            return
        try:
            if not self.monitor_sync_mode.get() and self.playlist_target.get() not in {"", "synced"} and item.media_type == "image":
                method = self.controller.set_image_multi({self.playlist_target.get(): item.path})
                self._save_last_applied(item, "single")
                self.set_status(f"Applied to {self.playlist_target.get()}: {item.name} via {method}")
            else:
                method = self.controller.apply(item)
                self._save_last_applied(item, "single")
                self.set_status(f"Applied: {item.name} via {method}")
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
        if self.monitor_sync_mode.get() or len(self._monitor_names()) <= 1:
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
                method = self.controller.apply(item)
                self._save_last_applied(item, "single")
                self._remember_random_pick(item)
                self.set_status(f"Random wallpaper applied: {item.name} via {method}")
                self.refresh_list()
                self._refresh_runtime_state()
            except Exception as exc:
                self.set_status(f"Error: {exc}")
            return

        output_to_path = {}
        chosen_items = []
        global_video = None
        for monitor in self._monitor_names():
            pool = [i for i in self._playlist_pool_for_target(monitor, supported_only=True) if i.media_type == "image"]
            if pool:
                item = self._pick_less_repetitive_random(pool)
                if item:
                    output_to_path[monitor] = item.path
                    chosen_items.append(item)
            else:
                vpool = [i for i in self._playlist_pool_for_target(monitor, supported_only=True) if i.media_type in {"video", "html"}]
                if vpool and global_video is None:
                    global_video = self._pick_less_repetitive_random(vpool)
        try:
            messages = []
            if output_to_path:
                messages.append(self.controller.set_image_multi(output_to_path))
                first_item = chosen_items[0] if chosen_items else None
                if first_item is not None:
                    self._save_last_applied(first_item, "multi")
                for item in chosen_items:
                    self._remember_random_pick(item)
            if global_video is not None:
                messages.append("video fallback: " + self.controller.apply(global_video))
                self._save_last_applied(global_video, "single")
                self._remember_random_pick(global_video)
            if messages:
                self.set_status("Random per-monitor applied via " + " | ".join(messages))
            else:
                self.set_status("No supported per-monitor playlist items available")
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
            self.set_status(f"{'Enabled' if self._item_enabled_for_target(item) else 'Disabled'} {item.name} for the playlist")
            return 'break'



    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.tree.focus(row)
            self._update_preview_for_selection()
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.context_menu.grab_release()
            except Exception:
                pass
        return "break"

    def rename_selected(self):
        item = self.primary_selected()
        if not item:
            return
        new_name = simple_input(self.root, "Rename Item", "New name:", item.name)
        if not new_name:
            return
        item.name = new_name.strip()
        self._save_items()
        self.refresh_view()
        self.set_status(f"Renamed: {item.name}")

    def _on_context_key(self, event=None):
        sel = self.tree.selection()
        if sel:
            row = sel[0]
            bbox = self.tree.bbox(row, "#1")
            if bbox:
                x = self.tree.winfo_rootx() + bbox[0] + 20
                y = self.tree.winfo_rooty() + bbox[1] + 20
            else:
                x = self.tree.winfo_rootx() + 40
                y = self.tree.winfo_rooty() + 40

            class E:
                pass

            e = E()
            e.x_root = x
            e.y_root = y
            e.y = 0
            return self._on_right_click(e)


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

    def _on_double_click(self, event):
        col = self.tree.identify_column(event.x)
        if col != '#1':
            self.apply_selected()

    def _tick_auto_change(self):
        self.random_job = None
        self._blink_on = True
        self._blink_job = None
        mode = self.auto_mode_var.get()
        if mode == "random":
            self.apply_random()
        elif mode == "playlist":
            self.apply_next_playlist()
        self._start_random_if_enabled()

    def _start_random_if_enabled(self):
        if self.random_job:
            self.root.after_cancel(self.random_job)
            self.random_job = None
        self._blink_on = True
        self._blink_job = None
        mode = self.auto_mode_var.get()
        self.store.data["auto_change_mode"] = mode
        self.store.data["random_enabled"] = (mode != "off")
        try:
            mins = max(1, int(self.auto_interval_var.get()))
        except Exception:
            mins = 10
            self.auto_interval_var.set(mins)
        self.store.data["random_interval_minutes"] = mins
        self.store.save()
        if mode != "off":
            self.random_job = self.root.after(mins * 60 * 1000, self._tick_auto_change)

    def _auto_controls_changed(self):
        self._update_auto_change_hint()
        self._start_random_if_enabled()
        self.root.after(1200, self._fullscreen_pause_tick)
        mode = self.auto_mode_var.get()
        if mode == "off":
            self.set_status("Auto change disabled")
        elif mode == "playlist":
            self.set_status(f"Auto change set to playlist every {int(self.auto_interval_var.get())} min using the All playlist")
        else:
            self.set_status(f"Auto change set to {mode} every {int(self.auto_interval_var.get())} min")

    def _get_last_applied_path(self) -> str:
        return str(self.store.data.get("last_applied_path", "") or "")

    def _playlist_enabled_supported(self) -> list[WallpaperItem]:
        return [i for i in self.all_items() if getattr(i, "enabled", True) and getattr(i, "supported", True)]

    def apply_next_playlist(self):
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
            method = self.controller.apply(item)
            self._save_last_applied(item, "single")
            self.set_status(f"Playlist wallpaper applied: {item.name} via {method}")
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
        ttk.Label(outer, text="Choose files or folders. Supported image and video formats will be imported into the local library.", style="Sub.TLabel").pack(anchor="w", pady=(0, 12))

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
            files = filedialog.askopenfilenames(parent=win, title="Select media files", filetypes=[("Supported media", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.webm *.mkv *.mov *.avi *.html *.htm"), ("All files", "*.*")])
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
        self._style_toplevel(win, title="Options", geometry="1040x720")
        try:
            self.root.update_idletasks()
            root_x = self.root.winfo_rootx()
            root_y = self.root.winfo_rooty()
            x = max(root_x + 24, 40)
            y = max(root_y + 90, 60)
            win.geometry(f"1040x720+{x}+{max(20, y - 60)}")
        except Exception:
            pass
        win.minsize(980, 620)
        try:
            win.transient(self.root)
        except Exception:
            pass

        outer = ttk.Frame(win, padding=8)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(header, text="Options", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Startup, preview, fullscreen behavior, audio, monitor sync, and Wallpaper Engine integration.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(0, 2))

        copy_var = tk.BooleanVar(value=bool(self.store.data.get("copy_into_library")))
        autostart_var = tk.BooleanVar(value=bool(self.store.data.get("autostart")))
        preview_var = tk.BooleanVar(value=bool(self.store.data.get("preview_visible", True)))
        pause_on_fullscreen_var = tk.BooleanVar(value=bool(self.store.data.get("pause_on_fullscreen", True)))
        we_var = tk.BooleanVar(value=bool(self.store.data.get("we_enabled", True)))
        show_unsupported_var = tk.BooleanVar(value=bool(self.store.data.get("show_unsupported_we", False)))
        volume_var = tk.IntVar(value=int(self.store.data.get("video_volume", 35)))
        mute_var = tk.BooleanVar(value=bool(self.store.data.get("video_mute", True)))
        sync_monitors_var = tk.BooleanVar(value=bool(self.store.data.get("monitor_sync_mode", True)))
        start_minimized_launch_var = tk.BooleanVar(value=bool(self.store.data.get("start_minimized_launch", self.store.data.get("start_minimized", False))))
        start_minimized_autostart_var = tk.BooleanVar(value=bool(self.store.data.get("start_minimized_autostart", self.store.data.get("start_minimized", False))))
        close_to_tray_var = tk.BooleanVar(value=bool(self.store.data.get("close_to_tray", True)))
        tray_close_notice_var = tk.BooleanVar(value=bool(self.store.data.get("tray_close_notice", True)))
        detected_monitors = ", ".join([self._monitor_display_name(m) for m in self.monitors]) or "None detected"
        selected_monitor_names = set(self._selected_monitor_names())

        info_bar = ttk.Frame(outer, style="Alt.TFrame", padding=(14, 12))
        info_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(
            info_bar,
            text="Auto change mode and interval stay directly above the library. The settings below focus on app behavior, startup, monitor sync, audio, and integrations.",
            style="PanelMuted.TLabel",
            wraplength=900,
            justify="left",
        ).pack(anchor="w")

        grid = ttk.Frame(outer)
        grid.pack(fill="both", expand=True)
        for col in range(2):
            grid.columnconfigure(col, weight=1, uniform="opt")
        for row in range(3):
            grid.rowconfigure(row, weight=1)

        def section(parent, title, row, column):
            box = ttk.LabelFrame(parent, text=f" {title} ")
            box.grid(
                row=row, column=column, sticky="nsew",
                padx=(0 if column == 0 else 5, 5 if column == 0 else 0),
                pady=4,
                ipadx=0, ipady=0
            )
            return box

        general_box = section(grid, "General", 0, 0)
        ttk.Checkbutton(general_box, text="Show preview panel", variable=preview_var).pack(anchor="w", padx=10, pady=(8, 2))
        ttk.Checkbutton(general_box, text="Copy imported files into the internal library", variable=copy_var).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(
            general_box,
            text="Pause video wallpaper while a fullscreen window is active (X11)",
            variable=pause_on_fullscreen_var,
        ).pack(anchor="w", padx=10, pady=(2, 8))

        startup_box = section(grid, "Startup", 1, 0)
        ttk.Checkbutton(startup_box, text="Start automatically on login", variable=autostart_var).pack(anchor="w", padx=10, pady=(8, 2))
        ttk.Checkbutton(startup_box, text="Start minimized when launched manually", variable=start_minimized_launch_var).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(startup_box, text="Start minimized on system startup", variable=start_minimized_autostart_var).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(startup_box, text="Keep app running in tray when clicking X", variable=close_to_tray_var).pack(anchor="w", padx=10, pady=(2, 2))
        ttk.Checkbutton(startup_box, text="Show a tray message when the window is closed to the applet", variable=tray_close_notice_var).pack(anchor="w", padx=10, pady=(2, 8))

        actions_box = section(grid, "App actions", 2, 0)
        ttk.Label(actions_box, text="Use Quit All Instances to fully close Mint Wallpaper Studio and stop every related process.", style="PanelMuted.TLabel", wraplength=360).pack(anchor="w", padx=10, pady=(8, 6))
        action_row = ttk.Frame(actions_box)
        action_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(action_row, text="Hide to Tray Now", command=self.hide_to_tray).pack(side="left")
        ttk.Button(action_row, text="Quit All Instances", command=self.quit_all_instances).pack(side="left", padx=(8, 0))

        playback_box = section(grid, "Video wallpaper audio", 0, 1)
        ttk.Checkbutton(playback_box, text="Mute video audio by default", variable=mute_var).pack(anchor="w", padx=10, pady=(8, 4))
        vol_row = ttk.Frame(playback_box)
        vol_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(vol_row, text="Default video volume", style="PanelBody.TLabel").pack(side="left")
        ttk.Scale(
            vol_row,
            from_=0,
            to=100,
            variable=volume_var,
            orient="horizontal",
            command=lambda _=None: self.controller.set_audio_options(int(volume_var.get()), bool(mute_var.get())),
        ).pack(side="left", fill="x", expand=True, padx=(12, 12))
        ttk.Label(vol_row, textvariable=volume_var, style="PanelMuted.TLabel", width=4).pack(side="left")

        monitors_box = section(grid, "Monitors & playlists", 1, 1)
        ttk.Checkbutton(monitors_box, text="Sync monitors to use one shared playlist", variable=sync_monitors_var).pack(anchor="w", padx=10, pady=(8, 2))
        monitor_vars = {}
        for mon in self.monitors:
            mon_name = self._monitor_display_name(mon)
            var = tk.BooleanVar(value=(mon_name in selected_monitor_names))
            monitor_vars[mon_name] = var
            ttk.Checkbutton(monitors_box, text=mon_name, variable=var).pack(anchor="w", padx=28, pady=2)
        ttk.Label(monitors_box, text="Detected monitors: " + detected_monitors, style="PanelMuted.TLabel", wraplength=360).pack(anchor="w", padx=10, pady=(4, 8))

        we_box = section(grid, "Wallpaper Engine integration", 2, 1)
        ttk.Checkbutton(we_box, text="Enable Wallpaper Engine library integration", variable=we_var).pack(anchor="w", padx=10, pady=(8, 2))
        we_dep_widgets = []
        show_unsupported_cb = ttk.Checkbutton(we_box, text="Show unsupported Wallpaper Engine items", variable=show_unsupported_var)
        show_unsupported_cb.pack(anchor="w", padx=28, pady=(2, 8))
        we_dep_widgets.append(show_unsupported_cb)
        ttk.Label(we_box, text="Preview, details, and scene inspector hide together when preview is off.", style="PanelMuted.TLabel", wraplength=360, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

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
            self.options_window = None
            try:
                win.destroy()
            except Exception:
                pass

        def save_options():
            we_was_enabled = bool(self.store.data.get("we_enabled", True))
            old_selected_monitors = set(self._selected_monitor_names())

            self.store.data["copy_into_library"] = copy_var.get()
            self.store.data["autostart"] = autostart_var.get()
            self.store.data["preview_visible"] = preview_var.get()
            self.store.data["pause_on_fullscreen"] = pause_on_fullscreen_var.get()
            self.pause_on_fullscreen_pref.set(pause_on_fullscreen_var.get())
            self.store.data["we_enabled"] = we_var.get()
            self.store.data["show_unsupported_we"] = show_unsupported_var.get() if we_var.get() else False
            self.store.data["video_volume"] = int(volume_var.get())
            self.store.data["video_mute"] = mute_var.get()
            self.store.data["monitor_sync_mode"] = sync_monitors_var.get()
            self.monitor_sync_mode.set(self.store.data["monitor_sync_mode"])
            self.store.data["start_minimized_launch"] = start_minimized_launch_var.get()
            self.start_minimized_launch_pref.set(start_minimized_launch_var.get())
            self.store.data["start_minimized_autostart"] = start_minimized_autostart_var.get()
            self.start_minimized_autostart_pref.set(start_minimized_autostart_var.get())
            self.store.data["start_minimized"] = bool(start_minimized_launch_var.get() or start_minimized_autostart_var.get())
            self.store.data["close_to_tray"] = close_to_tray_var.get()
            self.close_to_tray_pref.set(close_to_tray_var.get())
            self.store.data["tray_close_notice"] = tray_close_notice_var.get()

            chosen_monitors = [name for name, var in monitor_vars.items() if bool(var.get())]
            available_now = self._available_monitor_names()
            chosen_monitors = [name for name in chosen_monitors if name in available_now]
            self.store.data["selected_monitors"] = list(chosen_monitors)
            new_selected_monitors = set(chosen_monitors)
            removed_monitors = old_selected_monitors - new_selected_monitors

            self.preview_enabled.set(preview_var.get())
            self.show_unsupported_we.set(bool(self.store.data["show_unsupported_we"]))
            self.controller.set_audio_options(int(self.store.data["video_volume"]), bool(self.store.data["video_mute"]))
            if we_was_enabled and not we_var.get():
                self.we_items = []
                self.store.set_items(self.we_items, "we_items")

            if removed_monitors:
                try:
                    self.controller.stop_video()
                    self._update_pause_button()
                except Exception:
                    pass

            self.store.save()
            self._refresh_target_box()
            self._write_autostart()
            self._apply_we_visibility()
            self._apply_preview_visibility()
            self._start_random_if_enabled()
            self.refresh_list()
            self._update_pause_button()
            if removed_monitors:
                self.set_status("Disabled monitor(s) saved. Active video wallpaper was stopped so it no longer shows on removed displays.")
            close_options()

        footer = ttk.Frame(outer)
        footer.pack(fill="x", side="bottom", pady=(8, 0))
        ttk.Button(footer, text="Close", command=close_options).pack(side="left", ipadx=6)
        ttk.Button(footer, text="Save", style="Accent.TButton", command=save_options).pack(side="right", ipadx=10)
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
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="Card.TFrame", padding=10)
        right = ttk.Frame(body, style="Alt.TFrame", padding=10)
        body.add(left, weight=6)
        body.add(right, weight=4)

        topbar = ttk.Frame(left, style="Card.TFrame")
        topbar.pack(fill="x", pady=(0, 6))
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
        preview_wrap.pack(fill="x", pady=(0, 6))
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
            pystray.MenuItem("Open Options", schedule(self.show_options)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(pause_text if not html_running else "Pause unavailable for HTML", schedule(self.toggle_wallpaper_pause), enabled=lambda item: self.controller.is_video_running() and not self.wallpaper_paused_by_fullscreen and not html_running),
            pystray.MenuItem(mute_text, schedule(self.toggle_tray_mute)),
            pystray.MenuItem("Volume...", schedule(self.show_tray_volume_window)),
            pystray.MenuItem("Next Wallpaper", schedule(self.apply_random)),
            pystray.MenuItem("Hide to Tray Now", schedule(self.hide_to_tray)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit All Instances", schedule(lambda: self.quit_all_instances(confirm=False))),
        )

    def _schedule_on_ui(self, func, *args):
        try:
            self.root.after(0, lambda: func(*args))
        except Exception:
            pass

    def _apply_audio_settings(self, volume: int | None = None, mute: bool | None = None, save: bool = True):
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
        self.store.data["video_volume"] = volume
        self.store.data["video_mute"] = mute
        self.controller.set_audio_options(volume, mute)
        if save:
            self.store.save()
        mode = "muted" if mute else f"volume {volume}%"
        self.set_status(f"Video audio set to {mode}.")
        if not getattr(self, "tray_volume_win", None):
            self._update_tray_menu()

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
            self._apply_audio_settings(volume=value, mute=bool(mute_var.get()), save=False)

        scale.configure(command=lambda _=None: apply_from_scale())

        mute_btn = ttk.Checkbutton(frame, text="Mute wallpaper audio", variable=mute_var)
        mute_btn.pack(anchor="w", pady=(12, 8))

        def on_mute_changed(*_):
            muted = bool(mute_var.get())
            self._apply_audio_settings(volume=int(volume_var.get()), mute=muted, save=False)

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
            messagebox.showinfo("HTML Debug", "Select an HTML item first.")
            return

        html_path = Path(item.path)
        if not html_path.exists():
            messagebox.showerror("HTML Debug", "HTML file not found.")
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
        add_item("Open Options", self.show_options)
        menu.append(Gtk.SeparatorMenuItem())
        pause_label = "Pause unavailable for HTML" if getattr(self.controller, "is_html_running", lambda: False)() else "Pause Wallpaper"
        self.tray_pause_item = add_item(pause_label, self.toggle_wallpaper_pause, sensitive=(not getattr(self.controller, "is_html_running", lambda: False)()))
        self.tray_mute_item = add_item("Mute Wallpaper", self.toggle_tray_mute)
        add_item("Volume...", self.show_tray_volume_window)
        add_item("Next Wallpaper", self.apply_random)
        add_item("Hide to Tray Now", self.hide_to_tray)
        menu.append(Gtk.SeparatorMenuItem())
        add_item("Quit All Instances", lambda: self.quit_all_instances(confirm=False))
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
