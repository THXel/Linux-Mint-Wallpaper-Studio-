#!/usr/bin/env python3
from __future__ import annotations
import sys
import tkinter as tk

try:
    from tkinterdnd2 import TkinterDnD
except Exception:
    TkinterDnD = None

from mws.app import App

def main() -> None:
    kwargs = {"className": "MintWallpaperStudio"}
    kwargs = {"className": "mint-wallpaper-studio"}
    root = TkinterDnD.Tk(**kwargs) if TkinterDnD is not None else tk.Tk(**kwargs)
    start_minimized = "--minimized" in sys.argv
    launched_from_autostart = "--autostart" in sys.argv
    App(root, start_minimized=start_minimized, launched_from_autostart=launched_from_autostart)
    root.mainloop()

if __name__ == "__main__":
    main()
