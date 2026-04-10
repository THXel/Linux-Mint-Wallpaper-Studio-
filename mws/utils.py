from __future__ import annotations
import mimetypes
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
import re

IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff",
    ".avif", ".heic", ".heif", ".jfif", ".jxl", ".ico", ".ppm", ".pgm",
    ".pbm", ".pnm", ".tga", ".dds", ".pcx", ".xpm",
}
HTML_EXTS = {".html", ".htm"}
APPLICATION_EXTS = {".exe"}

VIDEO_EXTS = {
    ".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".wmv", ".flv",
    ".mpeg", ".mpg", ".m2v", ".ts", ".m2ts", ".mts", ".3gp", ".3g2",
    ".ogv", ".mxf", ".vob", ".asf", ".f4v", ".rm", ".rmvb", ".mjpeg",
}


def classify_media(path: Path) -> Optional[str]:
    suf = path.suffix.lower()
    if suf in IMAGE_EXTS:
        return "image"
    if suf in VIDEO_EXTS:
        return "video"
    mt, _ = mimetypes.guess_type(str(path))
    if suf in HTML_EXTS:
        return "html"
    if suf in APPLICATION_EXTS:
        return "application"
    if mt:
        if mt.startswith("image/"):
            return "image"
        if mt.startswith("video/"):
            return "video"
    return None


def scan_paths(paths: Iterable[Path]) -> List[Path]:
    found: List[Path] = []
    seen = set()
    for p in paths:
        if not p.exists():
            continue
        if p.is_file():
            if classify_media(p):
                rp = p.resolve()
                if rp not in seen:
                    found.append(rp)
                    seen.add(rp)
            continue
        for child in p.rglob("*"):
            if child.is_file() and classify_media(child):
                rp = child.resolve()
                if rp not in seen:
                    found.append(rp)
                    seen.add(rp)
    return found


def human_size(size: int) -> str:
    val = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if val < 1024 or unit == "TB":
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{size} B"


def human_dt(ts: float) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def probe_resolution(path: Path) -> tuple[int, int]:
    # images via PIL handled elsewhere; ffprobe fallback for video
    if shutil.which("ffprobe"):
        try:
            res = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)
                ],
                capture_output=True, text=True, check=False
            )
            if res.returncode == 0 and "x" in res.stdout:
                w, h = res.stdout.strip().split("x", 1)
                return int(w), int(h)
        except Exception:
            pass
    return (0, 0)


def open_in_file_manager(path: Path) -> None:
    p = path if path.is_dir() else path.parent
    subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def session_is_x11() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11"


def list_monitors() -> List[dict]:
    monitors: List[dict] = []
    if shutil.which("xrandr"):
        try:
            res = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if " connected" not in line:
                        continue
                    parts = line.split()
                    name = parts[0]
                    primary = " primary " in f" {line} "
                    geom = None
                    for part in parts:
                        if "+" in part and "x" in part:
                            geom = part
                            break
                    width = height = x = y = 0
                    if geom:
                        try:
                            wh, x, y = re.match(r"(\d+)x(\d+)\+(\d+)\+(\d+)", geom).groups()
                            width, height, x, y = map(int, (wh.split('x')[0], wh.split('x')[1], x, y))
                        except Exception:
                            try:
                                m = re.match(r"(\d+)x(\d+)\+(\d+)\+(\d+)", geom)
                                if m:
                                    width, height, x, y = map(int, m.groups())
                            except Exception:
                                pass
                    monitors.append({"name": name, "primary": primary, "width": width, "height": height, "x": x, "y": y})
        except Exception:
            pass
    if not monitors:
        monitors = [{"name": "default", "primary": True, "width": 0, "height": 0, "x": 0, "y": 0}]
    return monitors
