from __future__ import annotations
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from .models import WallpaperItem
from .utils import command_exists, session_is_x11, list_monitors


class WallpaperController:
    def __init__(self) -> None:
        self.video_proc: Optional[subprocess.Popen] = None
        self.html_proc: Optional[subprocess.Popen] = None
        self.current_item: Optional[WallpaperItem] = None
        self.video_volume: int = 35
        self.video_mute: bool = True
        self.video_paused: bool = False

    def set_audio_options(self, volume: int = 35, mute: bool = True) -> None:
        try:
            volume = int(volume)
        except Exception:
            volume = 35
        self.video_volume = max(0, min(100, volume))
        self.video_mute = bool(mute)

    def stop_video(self) -> None:
        procs = [p for p in (self.video_proc, self.html_proc) if p is not None]
        self.video_proc = None
        self.html_proc = None
        self.video_paused = False
        if not procs:
            return
        for proc in procs:
            try:
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=2.5)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass

    def is_video_running(self) -> bool:
        proc = self.video_proc
        return bool(proc and proc.poll() is None)

    def is_html_running(self) -> bool:
        proc = self.html_proc
        return bool(proc and proc.poll() is None)

    def is_any_wallpaper_running(self) -> bool:
        return self.is_video_running() or self.is_html_running() or bool(self.current_item)

    def pause_video(self) -> bool:
        proc = self.video_proc
        if not proc or proc.poll() is not None:
            self.video_paused = False
            return False
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGSTOP)
            self.video_paused = True
            return True
        except Exception:
            return False

    def resume_video(self) -> bool:
        proc = self.video_proc
        if not proc or proc.poll() is not None:
            self.video_paused = False
            return False
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGCONT)
            self.video_paused = False
            return True
        except Exception:
            return False

    def _run(self, cmd: List[str]) -> bool:
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return res.returncode == 0
        except Exception:
            return False


    def set_image_multi(self, output_to_path: dict[str, str]) -> str:
        self.stop_video()
        if not output_to_path:
            raise RuntimeError("No monitor wallpaper mapping provided.")
        resolved = {name: str(Path(path).resolve()) for name, path in output_to_path.items() if Path(path).exists()}
        if not resolved:
            raise RuntimeError("No valid image files found for the selected monitors.")
        methods = []
        if session_is_x11() and command_exists("xwallpaper"):
            cmd = ["xwallpaper"]
            for output, path in resolved.items():
                cmd.extend(["--output", output, "--zoom", path])
            if self._run(cmd):
                methods.append("xwallpaper-per-monitor")
                first = next(iter(resolved.values()))
                self.current_item = WallpaperItem(path=first, media_type="image", name=Path(first).stem)
                return ", ".join(methods)
        # fallback to applying the first image globally
        first = next(iter(resolved.values()))
        return self.set_image(first)

    def set_image(self, path: str) -> str:
        self.stop_video()
        p = Path(path).resolve()
        if not p.exists():
            raise RuntimeError("File not found.")
        uri = p.as_uri()
        methods = []
        self._run(["gsettings", "set", "org.cinnamon.desktop.background.slideshow", "slideshow-enabled", "false"])
        if self._run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-options", "zoom"]):
            methods.append("gsettings:picture-options")
        if self._run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri]):
            methods.append("gsettings:picture-uri")
        if session_is_x11():
            if command_exists("xwallpaper") and self._run(["xwallpaper", "--zoom", str(p)]):
                methods.append("xwallpaper")
            elif command_exists("feh") and self._run(["feh", "--bg-fill", str(p)]):
                methods.append("feh")
        self.current_item = WallpaperItem(path=str(p), media_type="image", name=p.stem)
        return ", ".join(methods) if methods else "image"

    def set_video(self, path: str) -> str:
        self.stop_video()
        p = Path(path).resolve()
        if not p.exists():
            raise RuntimeError("Video file not found.")
        if not command_exists("xwinwrap"):
            raise RuntimeError("xwinwrap was not found.")
        if not command_exists("mpv"):
            raise RuntimeError("mpv was not found.")

        audio_args = ["--mute=yes"] if self.video_mute else ["--mute=no", f"--volume={self.video_volume}"]
        base = [
            "xwinwrap", "-fs", "-fdt", "-ni", "-nf", "-un", "-s", "-st", "-sp", "-b",
            "--",
            "mpv", "-wid", "WID",
            "--loop-file=inf",
            *audio_args,
            "--no-osc",
            "--no-input-default-bindings",
            "--panscan=1.0",
            "--hwdec=auto-safe",
            str(p),
        ]
        fallback = [
            "xwinwrap", "-fs", "-fdt", "-ni", "-nf", "-un", "-s", "-st", "-sp", "-b", "-ovr",
            "--",
            "mpv", "-wid", "WID",
            "--loop-file=inf",
            *audio_args,
            "--no-osc",
            "--no-input-default-bindings",
            "--panscan=1.0",
            "--hwdec=auto-safe",
            str(p),
        ]
        errors = []
        for cmd, label in ((base, "xwinwrap"), (fallback, "xwinwrap+ovr")):
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid,
                )
                time.sleep(0.8)
                if proc.poll() is None:
                    self.video_proc = proc
                    self.video_paused = False
                    self.current_item = WallpaperItem(path=str(p), media_type="video", name=p.stem)
                    mode = "muted" if self.video_mute else f"volume {self.video_volume}%"
                    return f"{label} ({mode})"
                errors.append(f"{label}: exit {proc.returncode}")
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        raise RuntimeError("Video wallpaper could not be started. " + " | ".join(errors))


    def set_html(self, path: str) -> str:
        self.stop_video()
        p = Path(path).resolve()
        if not p.exists():
            raise RuntimeError("HTML file not found.")
        runner = Path(__file__).resolve().parent / "html_desktop_window.py"
        if not runner.exists():
            raise RuntimeError("HTML desktop runner is missing.")
        cmd = ["python3", str(runner), str(p)]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            time.sleep(1.2)
            if proc.poll() is None:
                self.html_proc = proc
                self.video_paused = False
                self.current_item = WallpaperItem(path=str(p), media_type="html", name=p.stem)
                return "html-desktop-window"
            raise RuntimeError(f"html-desktop-window: exit {proc.returncode}")
        except Exception as exc:
            raise RuntimeError("HTML wallpaper could not be started. " + str(exc))

    def apply(self, item: WallpaperItem) -> str:
        if item.media_type == "image":
            return self.set_image(item.path)
        if item.media_type == "video":
            return self.set_video(item.path)
        if item.media_type == "html":
            return self.set_html(item.path)
        raise RuntimeError("Unsupported media type.")
