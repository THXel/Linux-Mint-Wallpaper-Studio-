from __future__ import annotations
import os
import shutil
import signal
import socket
import json
import subprocess
import tempfile
import time
import threading
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image
except Exception:
    Image = None
from .models import WallpaperItem
from .utils import command_exists, session_is_x11, list_monitors
from .config import CONFIG_DIR, DEBUG_LOG_FILE


class WallpaperController:
    def __init__(self) -> None:
        self.video_proc: Optional[subprocess.Popen] = None
        self.html_proc: Optional[subprocess.Popen] = None
        self.app_proc: Optional[subprocess.Popen] = None
        self.current_item: Optional[WallpaperItem] = None
        self.video_volume: int = 35
        self.video_mute: bool = True
        self.video_paused: bool = False
        self.video_ipc_path: Optional[str] = None
        self.video_procs: List[subprocess.Popen] = []
        self.video_ipc_paths: List[str] = []
        self.video_monitor_map: dict[str, str] = {}
        self.video_monitor_ipc_map: dict[str, str] = {}
        self.video_monitor_proc_map: dict[str, subprocess.Popen] = {}
        self.video_audio_enabled_monitors: list[str] = []
        self._generated_wallpaper_path: Optional[str] = None
        self._app_launch_token: int = 0
        self.app_wine_prefix: Optional[str] = None


    def _debug(self, message: str) -> None:
        return

    def set_audio_monitor_enabled(self, monitors: list[str] | None = None) -> None:
        self.video_audio_enabled_monitors = list(monitors or [])
        try:
            self.apply_audio_live()
        except Exception:
            pass

    def set_audio_options(self, volume: int = 35, mute: bool = True) -> None:
        try:
            volume = int(volume)
        except Exception:
            volume = 35
        self.video_volume = max(0, min(100, volume))
        self.video_mute = bool(mute)
        try:
            self.apply_audio_live()
        except Exception:
            pass

    def _cleanup_generated_wallpaper(self) -> None:
        path = self._generated_wallpaper_path
        self._generated_wallpaper_path = None
        if not path:
            return
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass

    def _cleanup_video_ipc(self) -> None:
        paths = []
        if self.video_ipc_path:
            paths.append(self.video_ipc_path)
        paths.extend([p for p in self.video_ipc_paths if p])
        self.video_ipc_path = None
        self.video_ipc_paths = []
        self.video_monitor_map = {}
        self.video_monitor_ipc_map = {}
        self.video_monitor_proc_map = {}
        seen = set()
        for path in paths:
            if not path or path in seen:
                continue
            seen.add(path)
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass

    def _send_mpv_ipc_command(self, command: list) -> bool:
        procs = [p for p in ([self.video_proc] + list(self.video_procs)) if p is not None]
        proc_alive = any(p.poll() is None for p in procs)
        paths = []
        if self.video_ipc_path:
            paths.append(self.video_ipc_path)
        paths.extend([p for p in self.video_ipc_paths if p])
        paths = list(dict.fromkeys(paths))
        if not paths or not proc_alive:
            self._debug(f"ipc command skipped command={command!r} paths={paths!r} proc_alive={proc_alive}")
            return False
        payload = (json.dumps({"command": command}) + "\n").encode("utf-8")
        overall = False
        for path in paths:
            ok_path = False
            for attempt in range(1, 7):
                if not os.path.exists(path):
                    time.sleep(0.05)
                    continue
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(0.75)
                        client.connect(path)
                        client.sendall(payload)
                        response = b""
                        try:
                            while not response.endswith(b"\n"):
                                chunk = client.recv(4096)
                                if not chunk:
                                    break
                                response += chunk
                        except Exception:
                            pass
                    if not response:
                        self._debug(f"ipc command no-response attempt={attempt} command={command!r} path={path!r}")
                        time.sleep(0.05)
                        continue
                    try:
                        data = json.loads(response.decode("utf-8", errors="replace").strip())
                    except Exception as exc:
                        self._debug(f"ipc command bad-json attempt={attempt} command={command!r} path={path!r} response={response!r} exc={exc}")
                        time.sleep(0.05)
                        continue
                    err = str(data.get("error", "")).lower()
                    ok = err == "success"
                    self._debug(f"ipc command reply attempt={attempt} command={command!r} path={path!r} ok={ok} data={data!r}")
                    if ok:
                        ok_path = True
                        overall = True
                        break
                except Exception as exc:
                    self._debug(f"ipc command exception attempt={attempt} command={command!r} path={path!r} exc={exc}")
                    time.sleep(0.05)
            if not ok_path:
                self._debug(f"ipc command failed for path={path!r} command={command!r}")
        return overall

    def _send_mpv_ipc_command_to_path(self, path: str, command: list) -> bool:
        if not path:
            return False
        old_main = self.video_ipc_path
        old_paths = list(self.video_ipc_paths)
        try:
            self.video_ipc_path = path
            self.video_ipc_paths = [path]
            return self._send_mpv_ipc_command(command)
        finally:
            self.video_ipc_path = old_main
            self.video_ipc_paths = old_paths

    def apply_audio_live(self) -> bool:
        procs = [p for p in ([self.video_proc] + list(self.video_procs)) if p is not None]
        if not procs or not any(p.poll() is None for p in procs):
            return False
        if self.video_monitor_ipc_map:
            overall = False
            allowed = set(self.video_audio_enabled_monitors or [])
            for monitor, path in list(self.video_monitor_ipc_map.items()):
                if not path or not os.path.exists(path):
                    continue
                mute_this = bool(self.video_mute) or (bool(allowed) and monitor not in allowed)
                ok1 = self._send_mpv_ipc_command_to_path(path, ["set_property", "mute", bool(mute_this)])
                if ok1 and not mute_this:
                    self._send_mpv_ipc_command_to_path(path, ["set_property", "volume", int(self.video_volume)])
                overall = overall or ok1
            return overall
        ok1 = self._send_mpv_ipc_command(["set_property", "mute", bool(self.video_mute)])
        if self.video_mute:
            return ok1
        ok2 = self._send_mpv_ipc_command(["set_property", "volume", int(self.video_volume)])
        return ok1 and ok2

    def reapply_current_video_with_audio(self) -> bool:
        if self.apply_audio_live():
            return True

        item = self.current_item
        if not item or item.media_type != "video":
            return False

        path = item.path
        if not path:
            return False

        try:
            self.set_video(path)
            return True
        except Exception:
            return False

    def _find_processes_for_wine_prefix(self, prefix: Optional[str]) -> list[int]:
        if not prefix:
            return []
        matched: list[int] = []
        proc_root = Path('/proc')
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == os.getpid():
                continue
            try:
                env_raw = (entry / 'environ').read_bytes()
            except Exception:
                continue
            marker = f'WINEPREFIX={prefix}'.encode('utf-8', errors='ignore')
            if marker not in env_raw:
                continue
            try:
                cmdline = (entry / 'cmdline').read_text('utf-8', errors='ignore').replace('\x00', ' ')
            except Exception:
                cmdline = ''
            if 'wine' not in cmdline.lower() and 'wineserver' not in cmdline.lower():
                continue
            matched.append(pid)
        return matched

    def _terminate_pids(self, pids: list[int], sig: int, label: str) -> None:
        for pid in pids:
            try:
                os.kill(pid, sig)
                self._debug(f'{label} pid={pid}')
            except Exception as exc:
                self._debug(f'{label} failed pid={pid} exc={exc}')

    def _wait_for_wine_prefix_exit(self, prefix: Optional[str], timeout: float = 8.0) -> bool:
        deadline = time.time() + max(0.5, timeout)
        while time.time() < deadline:
            if not self._find_processes_for_wine_prefix(prefix):
                return True
            time.sleep(0.15)
        return not self._find_processes_for_wine_prefix(prefix)

    def _shutdown_app_wine_prefix(self, prefix: Optional[str]) -> None:
        if not prefix:
            return
        wineserver = shutil.which('wineserver')
        env = os.environ.copy()
        env['WINEPREFIX'] = prefix
        if wineserver:
            for cmd in ([wineserver, '-k'], [wineserver, '-w']):
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, env=env, timeout=10)
                except Exception as exc:
                    self._debug(f'wineserver shutdown step failed cmd={cmd!r} exc={exc}')
        pids = self._find_processes_for_wine_prefix(prefix)
        if pids:
            self._terminate_pids(pids, signal.SIGTERM, 'wineprefix cleanup SIGTERM')
            time.sleep(0.45)
            still = self._find_processes_for_wine_prefix(prefix)
            if still:
                self._terminate_pids(still, signal.SIGKILL, 'wineprefix cleanup SIGKILL')
        self._wait_for_wine_prefix_exit(prefix, timeout=8.0)

    def _application_prefix_dir(self) -> Path:
        return CONFIG_DIR / "wineprefix" / "applications"

    def get_application_runtime_info(self) -> dict:
        prefix_dir = self._application_prefix_dir()
        wine_bin = shutil.which("wine-staging") or shutil.which("wine") or shutil.which("wine64")
        wineserver_bin = shutil.which("wineserver")
        winetricks_bin = shutil.which("winetricks")
        marker = prefix_dir / ".mws_runtime.json"
        info = {
            "prefix_dir": str(prefix_dir),
            "prefix_exists": prefix_dir.exists(),
            "wine_bin": wine_bin or "",
            "wine_preferred": "staging" if (wine_bin and "staging" in Path(wine_bin).name) else "standard",
            "wineserver_bin": wineserver_bin or "",
            "winetricks_bin": winetricks_bin or "",
            "runtime_marker": str(marker),
            "runtime_initialized": marker.exists(),
            "dxvk_status": "unknown",
            "mono_status": "unknown",
        }
        if marker.exists():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    info.update({
                        "runtime_initialized": True,
                        "dxvk_status": str(data.get("dxvk_status", info["dxvk_status"])),
                        "mono_status": str(data.get("mono_status", info["mono_status"])),
                        "corefonts_status": str(data.get("corefonts_status", "unknown")),
                        "gecko_status": str(data.get("gecko_status", "unknown")),
                        "wine_version": str(data.get("wine_version", "")),
                        "wine_preferred": str(data.get("wine_preferred", info["wine_preferred"])),
                        "initialized_at": str(data.get("initialized_at", "")),
                    })
            except Exception:
                pass
        return info

    def initialize_application_runtime(self, force_reset: bool = False) -> dict:
        wine_bin = shutil.which("wine-staging") or shutil.which("wine") or shutil.which("wine64")
        wineserver_bin = shutil.which("wineserver")
        if not wine_bin or not wineserver_bin:
            raise RuntimeError("Wine and wineserver are required to initialize the managed application runtime.")

        prefix_dir = self._application_prefix_dir()
        marker = prefix_dir / ".mws_runtime.json"
        if force_reset and prefix_dir.exists():
            try:
                self._shutdown_app_wine_prefix(str(prefix_dir))
            except Exception:
                pass
            shutil.rmtree(prefix_dir, ignore_errors=True)

        prefix_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["WINEPREFIX"] = str(prefix_dir)
        env.setdefault("WINEDEBUG", "-all")
        env.setdefault("WINEDLLOVERRIDES", "winemenubuilder.exe=d")
        env.setdefault("DXVK_STATE_CACHE", "0")
        env.setdefault("MESA_NO_ERROR", "1")
        env.setdefault("WINEARCH", "win64")
        env.setdefault("DXVK_HUD", "0")
        env.setdefault("DXVK_LOG_LEVEL", "none")
        env.setdefault("WINE_LARGE_ADDRESS_AWARE", "1")

        steps = []
        def _run_step(cmd: list[str], timeout: int = 180):
            self._debug(f"application runtime step cmd={cmd!r}")
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, env=env, timeout=timeout)
            steps.append({"cmd": cmd, "returncode": int(res.returncode)})
            return res.returncode == 0

        ok_boot = _run_step([wine_bin, "wineboot", "-u"], timeout=240)
        _run_step([wineserver_bin, "-w"], timeout=120)
        _run_step([wine_bin, "reg", "add", r"HKCU\Software\Wine", "/v", "Version", "/d", "win10", "/f"], timeout=120)
        _run_step([wine_bin, "reg", "add", r"HKCU\Software\Wine\Explorer\Desktops", "/v", "WallpaperStudio", "/d", "1920x1080", "/f"], timeout=120)

        dxvk_status = "not-requested"
        mono_status = "managed-prefix"
        corefonts_status = "not-requested"
        gecko_status = "system-or-managed"
        winetricks_bin = shutil.which("winetricks")
        if winetricks_bin:
            # Optional helpers; ignore failures because coverage differs across distros.
            _run_step([winetricks_bin, "-q", "settings", "win10"], timeout=240)
            if _run_step([winetricks_bin, "-q", "dxvk"], timeout=900):
                dxvk_status = "installed-via-winetricks"
            else:
                dxvk_status = "winetricks-dxvk-failed"
            if _run_step([winetricks_bin, "-q", "corefonts"], timeout=900):
                corefonts_status = "installed-via-winetricks"
            else:
                corefonts_status = "winetricks-corefonts-failed"
            _run_step([winetricks_bin, "-q", "renderer=gl"], timeout=240)
        else:
            dxvk_status = "winetricks-not-found"
            corefonts_status = "winetricks-not-found"

        try:
            wine_ver = subprocess.run([wine_bin, "--version"], capture_output=True, text=True, check=False, timeout=20).stdout.strip()
        except Exception:
            wine_ver = ""
        meta = {
            "initialized_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "wine_version": wine_ver,
            "wine_preferred": "staging" if (wine_bin and "staging" in Path(wine_bin).name) else "standard",
            "dxvk_status": dxvk_status,
            "mono_status": mono_status,
            "corefonts_status": corefonts_status,
            "gecko_status": gecko_status,
            "steps": steps,
            "ok_boot": bool(ok_boot),
        }
        marker.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        self._debug(f"application runtime initialized prefix={str(prefix_dir)!r} ok_boot={ok_boot} dxvk_status={dxvk_status} mono_status={mono_status}")
        return meta

    def reset_application_runtime(self) -> None:
        prefix_dir = self._application_prefix_dir()
        self._debug(f"application runtime reset requested prefix={str(prefix_dir)!r}")
        self._shutdown_app_wine_prefix(str(prefix_dir))
        shutil.rmtree(prefix_dir, ignore_errors=True)

    def _cleanup_orphan_wallpaper_processes(self) -> None:
        patterns = [
            "xwinwrap",
            "mint-wallpaper-studio-mpv-",
            "mpv -wid ",
            "mpv --wid=",
        ]
        try:
            res = subprocess.run(["pgrep", "-af", "."], capture_output=True, text=True, check=False)
            lines = (res.stdout or "").splitlines()
        except Exception as exc:
            self._debug(f"orphan cleanup pgrep failed: {exc}")
            lines = []
        seen = set()
        for line in lines:
            try:
                pid_txt, cmd = line.strip().split(" ", 1)
                pid = int(pid_txt)
            except Exception:
                continue
            if pid == os.getpid() or pid in seen:
                continue
            if not any(pat in cmd for pat in patterns):
                continue
            seen.add(pid)
            try:
                os.kill(pid, signal.SIGTERM)
                self._debug(f"orphan cleanup SIGTERM pid={pid} cmd={cmd!r}")
            except Exception as exc:
                self._debug(f"orphan cleanup SIGTERM failed pid={pid} exc={exc}")
        if seen:
            time.sleep(0.35)
            for pid in list(seen):
                try:
                    os.kill(pid, 0)
                except Exception:
                    continue
                try:
                    os.kill(pid, signal.SIGKILL)
                    self._debug(f"orphan cleanup SIGKILL pid={pid}")
                except Exception as exc:
                    self._debug(f"orphan cleanup SIGKILL failed pid={pid} exc={exc}")
        # remove stale sockets
        try:
            tmpdir = Path(tempfile.gettempdir())
            for sock in tmpdir.glob("mint-wallpaper-studio-mpv-*.sock"):
                try:
                    sock.unlink(missing_ok=True)
                    self._debug(f"orphan cleanup removed socket={str(sock)!r}")
                except Exception:
                    pass
        except Exception:
            pass

    def stop_video(self) -> None:
        self._app_launch_token += 1
        had_app = self.app_proc is not None
        app_prefix = self.app_wine_prefix
        procs = [p for p in ([self.video_proc] + list(self.video_procs) + [self.html_proc, self.app_proc]) if p is not None]
        self.video_proc = None
        self.video_procs = []
        self.video_monitor_proc_map = {}
        self.html_proc = None
        self.app_proc = None
        self.app_wine_prefix = None
        self.video_paused = False
        self._cleanup_video_ipc()
        self._cleanup_generated_wallpaper()
        if not procs and not had_app:
            return
        for proc in procs:
            try:
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3.0)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        if had_app:
            self._shutdown_app_wine_prefix(app_prefix)
            self._wait_for_wine_prefix_exit(app_prefix, timeout=8.0)
            # give the window manager a short moment to forget old Wine windows
            time.sleep(0.35)
        self._cleanup_orphan_wallpaper_processes()

    def is_video_running(self) -> bool:
        procs = [p for p in ([self.video_proc] + list(self.video_procs)) if p is not None]
        return any(p.poll() is None for p in procs)

    def is_app_running(self) -> bool:
        proc = self.app_proc
        return bool(proc and proc.poll() is None)

    def is_html_running(self) -> bool:
        proc = self.html_proc
        return bool(proc and proc.poll() is None)

    def is_any_wallpaper_running(self) -> bool:
        return self.is_video_running() or self.is_html_running() or self.is_app_running() or bool(self.current_item)

    def pause_video(self) -> bool:
        procs = [p for p in ([self.video_proc] + list(self.video_procs)) if p is not None]
        if not procs or not any(p.poll() is None for p in procs):
            self.video_paused = False
            self._debug("pause_video skipped because no active video process")
            return False
        try:
            if self._send_mpv_ipc_command(["set_property", "pause", True]):
                self.video_paused = True
                self._debug("pause_video succeeded via mpv ipc")
                return True
        except Exception as exc:
            self._debug(f"pause_video ipc exception: {exc}")
        try:
            for proc in procs:
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGSTOP)
            self.video_paused = True
            self._debug("pause_video succeeded via SIGSTOP fallback")
            return True
        except Exception as exc:
            self._debug(f"pause_video failed via SIGSTOP fallback: {exc}")
            return False

    def resume_video(self) -> bool:
        procs = [p for p in ([self.video_proc] + list(self.video_procs)) if p is not None]
        if not procs or not any(p.poll() is None for p in procs):
            self.video_paused = False
            self._debug("resume_video skipped because no active video process")
            return False
        try:
            if self._send_mpv_ipc_command(["set_property", "pause", False]):
                self.video_paused = False
                self._debug("resume_video succeeded via mpv ipc")
                return True
        except Exception as exc:
            self._debug(f"resume_video ipc exception: {exc}")
        try:
            for proc in procs:
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGCONT)
            self.video_paused = False
            self._debug("resume_video succeeded via SIGCONT fallback")
            return True
        except Exception as exc:
            self._debug(f"resume_video failed via SIGCONT fallback: {exc}")
            return False

    def _run(self, cmd: List[str]) -> bool:
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return res.returncode == 0
        except Exception:
            return False

    def _list_x11_windows(self) -> list[dict]:
        if not session_is_x11() or not command_exists("wmctrl"):
            return []
        try:
            res = subprocess.run(["wmctrl", "-lpGx"], capture_output=True, text=True, check=False)
            out = []
            for raw in (res.stdout or "").splitlines():
                parts = raw.split(None, 8)
                if len(parts) < 9:
                    continue
                win_id, desktop, pid, x, y, w, h, wm_class, title = parts
                try:
                    out.append({
                        "id": win_id.lower(),
                        "desktop": int(desktop),
                        "pid": int(pid),
                        "x": int(x),
                        "y": int(y),
                        "w": int(w),
                        "h": int(h),
                        "class": wm_class.lower(),
                        "title": title.strip(),
                    })
                except Exception:
                    continue
            return out
        except Exception:
            return []

    def _desktop_bounds(self) -> tuple[int, int, int, int]:
        monitors = list_monitors()
        if not monitors:
            return 0, 0, 1920, 1080
        min_x = min(int(m.get("x", 0)) for m in monitors)
        min_y = min(int(m.get("y", 0)) for m in monitors)
        max_x = max(int(m.get("x", 0)) + max(1, int(m.get("width", 0) or 0)) for m in monitors)
        max_y = max(int(m.get("y", 0)) + max(1, int(m.get("height", 0) or 0)) for m in monitors)
        width = max(1280, max_x - min_x)
        height = max(720, max_y - min_y)
        return min_x, min_y, width, height

    def _primary_monitor_bounds(self) -> tuple[int, int, int, int]:
        monitors = list_monitors()
        primary = None
        for m in monitors:
            if isinstance(m, dict) and m.get("primary"):
                primary = m
                break
        if primary is None and monitors:
            primary = monitors[0]
        if primary is None:
            return 0, 0, 1920, 1080
        x = int(primary.get("x", 0))
        y = int(primary.get("y", 0))
        width = max(1, int(primary.get("width", 1920) or 1920))
        height = max(1, int(primary.get("height", 1080) or 1080))
        return x, y, width, height

    def _apply_window_desktop_hints(self, win_id: str) -> bool:
        if not win_id or not session_is_x11():
            return False
        x, y, width, height = self._primary_monitor_bounds()
        cmds = []
        if command_exists("wmctrl"):
            cmds.extend([
                ["wmctrl", "-i", "-r", win_id, "-b", "add,below,sticky,skip_taskbar,skip_pager"],
                ["wmctrl", "-i", "-r", win_id, "-t", "-1"],
                ["wmctrl", "-i", "-r", win_id, "-e", f"0,{x},{y},{width},{height}"],
            ])
        if command_exists("xprop"):
            cmds.extend([
                ["xprop", "-id", win_id, "-f", "_NET_WM_STATE", "32a", "-set", "_NET_WM_STATE", "_NET_WM_STATE_BELOW,_NET_WM_STATE_STICKY,_NET_WM_STATE_SKIP_TASKBAR,_NET_WM_STATE_SKIP_PAGER"],
                ["xprop", "-id", win_id, "-f", "_NET_WM_WINDOW_TYPE", "32a", "-set", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DESKTOP"],
            ])
        if command_exists("xdotool"):
            cmds.extend([
                ["xdotool", "windowstate", "--remove", "MAXIMIZED_HORZ", win_id],
                ["xdotool", "windowstate", "--remove", "MAXIMIZED_VERT", win_id],
                ["xdotool", "windowstate", "--remove", "FULLSCREEN", win_id],
                ["xdotool", "windowsize", win_id, str(width), str(height)],
                ["xdotool", "windowmove", win_id, str(x), str(y)],
                ["xdotool", "set_window", "--overrideredirect", "1", win_id],
                ["xdotool", "windowlower", win_id],
            ])
        ok = False
        for cmd in cmds:
            ok = self._run(cmd) or ok
        return ok

    def _find_application_window(self, proc: subprocess.Popen, exe_path: Path, before_ids: set[str]) -> str | None:
        expected_tokens = {exe_path.stem.lower(), exe_path.name.lower(), "wine"}
        folder_name = exe_path.parent.name.lower()
        if folder_name:
            expected_tokens.add(folder_name)
        deadline = time.time() + 18.0
        while time.time() < deadline:
            windows = self._list_x11_windows()
            for win in reversed(windows):
                wid = win.get("id")
                if not wid or wid in before_ids:
                    continue
                title_l = str(win.get("title") or "").lower()
                class_l = str(win.get("class") or "").lower()
                pid = int(win.get("pid") or 0)
                if pid == proc.pid and wid not in before_ids:
                    return wid
                haystack = f"{title_l} {class_l}"
                if any(token for token in expected_tokens if token and token in haystack):
                    return wid
            time.sleep(0.35)
        return None

    def _watch_application_window(self, proc: subprocess.Popen, exe_path: Path, before_ids: set[str], token: int) -> None:
        try:
            win_id = self._find_application_window(proc, exe_path, before_ids)
            if not win_id:
                self._debug(f'application window watcher found no window for {exe_path.name!r}')
                return
            self._debug(f'application window watcher matched win_id={win_id} exe={exe_path.name!r}')
            deadline = time.time() + 24.0
            fast_until = time.time() + 4.0
            while time.time() < deadline:
                if token != self._app_launch_token or self.app_proc is not proc or proc.poll() is not None:
                    return
                self._apply_window_desktop_hints(win_id)
                time.sleep(0.12 if time.time() < fast_until else 0.35)
        except Exception as exc:
            self._debug(f'application window watcher exception exe={exe_path.name!r} exc={exc}')
            return


    def set_image_stretch(self, path: str) -> str:
        p = Path(path).resolve()
        if not p.exists():
            raise RuntimeError("File not found.")
        monitors = list_monitors()
        if not monitors or Image is None:
            return self.set_image(str(p))
        try:
            min_x = min(int(m.get("x", 0)) for m in monitors)
            min_y = min(int(m.get("y", 0)) for m in monitors)
            max_x = max(int(m.get("x", 0)) + max(1, int(m.get("width", 0) or 0)) for m in monitors)
            max_y = max(int(m.get("y", 0)) + max(1, int(m.get("height", 0) or 0)) for m in monitors)
            width = max(1, max_x - min_x)
            height = max(1, max_y - min_y)
            with Image.open(p) as img:
                img = img.convert("RGB")
                resized = img.resize((width, height), getattr(Image, 'LANCZOS', Image.BICUBIC))
                out = CONFIG_DIR / f"stretch-{int(time.time()*1000)}.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                resized.save(out, format='PNG')
            self._cleanup_generated_wallpaper()
            self._generated_wallpaper_path = str(out)
            method = self.set_image(str(out))
            self.current_item = WallpaperItem(path=str(p), media_type="image", name=p.stem)
            return f"stretch ({method})"
        except Exception as exc:
            self._debug(f"set_image_stretch fallback path={str(p)!r} exc={exc}")
            return self.set_image(str(p))

    def _launch_xwinwrap_video(self, path: Path, ipc_path: str, geometry: tuple[int, int, int, int] | None = None, force_mute: bool | None = None, start_paused: bool = False) -> tuple[subprocess.Popen, str]:
        mute_now = self.video_mute if force_mute is None else bool(force_mute)
        audio_args = ["--mute=yes"] if mute_now else ["--mute=no", f"--volume={self.video_volume}"]
        common = [
            "--",
            "mpv", "-wid", "WID",
            "--loop-file=inf",
            f"--input-ipc-server={ipc_path}",
            *audio_args,
            *( ["--pause=yes"] if start_paused else [] ),
            "--no-osc",
            "--no-input-default-bindings",
            "--panscan=1.0",
            "--hwdec=auto-safe",
            str(path),
        ]
        base = ["xwinwrap"]
        if geometry is None:
            base.extend(["-fs", "-fdt", "-ni", "-nf", "-un", "-s", "-st", "-sp", "-b"])
        else:
            x, y, w, h = geometry
            base.extend(["-g", f"{w}x{h}+{x}+{y}", "-fdt", "-ni", "-nf", "-un", "-s", "-st", "-sp", "-b"])
        cmd = base + common
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
        return proc, "xwinwrap"


    def set_image_on_monitor(self, monitor: str, path: str, stop_video: bool = False) -> str:
        if stop_video:
            self.stop_video_monitor(monitor)
        p = Path(path).resolve()
        if not p.exists():
            raise RuntimeError("File not found.")
        if session_is_x11() and command_exists("xwallpaper"):
            cmd = ["xwallpaper", "--output", str(monitor), "--zoom", str(p)]
            if self._run(cmd):
                self.current_item = WallpaperItem(path=str(p), media_type="image", name=p.stem)
                return "xwallpaper-per-monitor"
        return self.set_image_multi({str(monitor): str(p)}, stop_video=stop_video)

    def stop_video_monitor(self, monitor: str) -> None:
        monitor = str(monitor or "")
        if not monitor:
            return
        proc = self.video_monitor_proc_map.pop(monitor, None)
        ipc = self.video_monitor_ipc_map.pop(monitor, None)
        self.video_monitor_map.pop(monitor, None)
        if proc is not None:
            try:
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3.0)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        if ipc:
            try:
                if os.path.exists(ipc):
                    os.unlink(ipc)
            except Exception:
                pass
        self.video_procs = [p for m,p in self.video_monitor_proc_map.items() if p is not None]
        self.video_ipc_paths = [path for _m,path in self.video_monitor_ipc_map.items() if path]
        self.video_proc = self.video_procs[0] if self.video_procs else None
        self.video_ipc_path = self.video_ipc_paths[0] if self.video_ipc_paths else None
        if not self.video_procs:
            self.video_paused = False

    def set_video_on_monitor(self, monitor: str, path: str, audio_enabled_monitors: list[str] | None = None) -> str:
        self._debug(f"set_video_on_monitor start monitor={monitor!r} path={path!r} app_running={self.is_app_running()} html_running={self.is_html_running()}")
        if self.is_app_running() or self.is_html_running():
            self._debug("set_video_on_monitor stopping app/html runtime before starting video")
            self.stop_video()
        monitor = str(monitor or "")
        p = Path(path).resolve()
        if not monitor or not p.exists():
            raise RuntimeError("Video file not found.")
        if not command_exists("xwinwrap"):
            raise RuntimeError("xwinwrap was not found.")
        if not command_exists("mpv"):
            raise RuntimeError("mpv was not found.")
        monitors_by_name = {m.get("name"): m for m in list_monitors() if m.get("name")}
        mon = monitors_by_name.get(monitor)
        if mon is None:
            raise RuntimeError("Monitor not found.")
        geom = (int(mon.get("x", 0)), int(mon.get("y", 0)), max(1, int(mon.get("width", 0) or 1)), max(1, int(mon.get("height", 0) or 1)))
        self.stop_video_monitor(monitor)
        ipc_path = os.path.join(tempfile.gettempdir(), f"mint-wallpaper-studio-mpv-{os.getpid()}-{monitor}-{int(time.time() * 1000)}.sock")
        allowed = set(audio_enabled_monitors or self.video_audio_enabled_monitors or [])
        proc, _label = self._launch_xwinwrap_video(p, ipc_path, geom, force_mute=(monitor not in allowed if allowed else None), start_paused=False)
        time.sleep(0.35)
        if proc.poll() is not None:
            raise RuntimeError(f"Per-monitor video wallpaper could not be started for {monitor}.")
        self.video_monitor_proc_map[monitor] = proc
        self.video_monitor_ipc_map[monitor] = ipc_path
        self.video_monitor_map[monitor] = str(p)
        self.video_procs = [pr for _m, pr in self.video_monitor_proc_map.items() if pr is not None]
        self.video_ipc_paths = [sock for _m, sock in self.video_monitor_ipc_map.items() if sock]
        self.video_proc = self.video_procs[0] if self.video_procs else proc
        self.video_ipc_path = self.video_ipc_paths[0] if self.video_ipc_paths else ipc_path
        self.video_audio_enabled_monitors = list(audio_enabled_monitors or self.video_audio_enabled_monitors or [])
        self.current_item = WallpaperItem(path=str(p), media_type="video", name=p.stem)
        self.apply_audio_live()
        return "per-monitor video"

    def set_video_multi(self, output_to_path: dict[str, str], audio_enabled_monitors: list[str] | None = None) -> str:
        self._debug(f"set_video_multi start outputs={output_to_path!r} app_running={self.is_app_running()} html_running={self.is_html_running()}")
        self.stop_video()
        if not output_to_path:
            raise RuntimeError("No monitor video mapping provided.")
        monitors_by_name = {m.get("name"): m for m in list_monitors() if m.get("name")}
        launches = []
        paths = []
        ipcs = []
        first_proc = None
        first_ipc = None
        first_item = None
        errors = []
        audio_allowed = set(audio_enabled_monitors or [])
        same_source = len({str(v) for v in output_to_path.values()}) == 1 and len(output_to_path) > 1
        for monitor, raw_path in output_to_path.items():
            mon = monitors_by_name.get(monitor)
            p = Path(raw_path).resolve()
            if mon is None or not p.exists():
                continue
            geom = (int(mon.get("x", 0)), int(mon.get("y", 0)), max(1, int(mon.get("width", 0) or 1)), max(1, int(mon.get("height", 0) or 1)))
            ipc_path = os.path.join(tempfile.gettempdir(), f"mint-wallpaper-studio-mpv-{os.getpid()}-{monitor}-{int(time.time() * 1000)}.sock")
            try:
                proc, label = self._launch_xwinwrap_video(p, ipc_path, geom, force_mute=(monitor not in audio_allowed if audio_allowed else None), start_paused=same_source)
                time.sleep(0.35)
                if proc.poll() is None:
                    launches.append(proc)
                    ipcs.append(ipc_path)
                    paths.append(f"{monitor}={p}")
                    if first_proc is None:
                        first_proc = proc
                        first_ipc = ipc_path
                        first_item = WallpaperItem(path=str(p), media_type="video", name=p.stem)
                else:
                    errors.append(f"{monitor}: exit {proc.returncode}")
            except Exception as exc:
                errors.append(f"{monitor}: {exc}")
        if not launches:
            self._cleanup_video_ipc()
            raise RuntimeError("Per-monitor video wallpaper could not be started. " + " | ".join(errors))
        self.video_proc = first_proc
        self.video_procs = list(launches)
        self.video_ipc_path = first_ipc
        self.video_ipc_paths = list(ipcs)
        self.video_paused = False
        self.current_item = first_item
        self.video_monitor_map = {str(k): str(v) for k, v in output_to_path.items()}
        self.video_monitor_ipc_map = {str(k): str(v) for k, v in zip(output_to_path.keys(), ipcs)}
        self.video_monitor_proc_map = {str(k): proc for k, proc in zip(output_to_path.keys(), launches)}
        self.video_audio_enabled_monitors = list(audio_enabled_monitors or [])
        if same_source and ipcs:
            time.sleep(0.2)
            for ipc in list(ipcs):
                old_main = self.video_ipc_path
                old_paths = list(self.video_ipc_paths)
                try:
                    self.video_ipc_path = ipc
                    self.video_ipc_paths = [ipc]
                    self._send_mpv_ipc_command(["set_property", "pause", False])
                finally:
                    self.video_ipc_path = old_main
                    self.video_ipc_paths = old_paths
        self._debug(f"set_video_multi success count={len(launches)} targets={paths!r} same_source={same_source}")
        mode = "muted" if self.video_mute else f"volume {self.video_volume}%"
        return f"per-monitor video ({mode})"

    def set_image_multi(self, output_to_path: dict[str, str], stop_video: bool = True) -> str:
        self._debug(f"set_image_multi start stop_video={stop_video} outputs={output_to_path!r} html_running={self.is_html_running()} app_running={self.is_app_running()} video_running={self.is_video_running()}")
        if stop_video:
            self.stop_video()
        elif self.is_app_running() or self.is_html_running():
            self._debug("set_image_multi stopping app/html runtime even though stop_video=False")
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
        self._debug(f"set_image_multi fallback_to_global first={first!r} resolved={resolved!r}")
        return self.set_image(first)

    def set_image(self, path: str) -> str:
        self._debug(f"set_image start path={path!r} app_running={self.is_app_running()} html_running={self.is_html_running()} video_running={self.is_video_running()}")
        self.stop_video()
        self._cleanup_generated_wallpaper()
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
        self._cleanup_generated_wallpaper()
        p = Path(path).resolve()
        if not p.exists():
            raise RuntimeError("Video file not found.")
        if not command_exists("xwinwrap"):
            raise RuntimeError("xwinwrap was not found.")
        if not command_exists("mpv"):
            raise RuntimeError("mpv was not found.")

        ipc_path = os.path.join(tempfile.gettempdir(), f"mint-wallpaper-studio-mpv-{os.getpid()}-{int(time.time() * 1000)}.sock")
        self._cleanup_video_ipc()
        self._debug(f"set_video start path={str(p)!r} ipc_path={ipc_path!r} mute={self.video_mute} volume={self.video_volume}")
        errors = []
        for _label in ("xwinwrap",):
            try:
                proc, label = self._launch_xwinwrap_video(p, ipc_path, None)
                time.sleep(0.8)
                if proc.poll() is None:
                    self.video_proc = proc
                    self.video_procs = [proc]
                    self.video_ipc_path = ipc_path
                    self.video_ipc_paths = [ipc_path]
                    self.video_paused = False
                    self._debug(f"set_video success label={label!r} pid={proc.pid} ipc_exists={os.path.exists(ipc_path)}")
                    self.current_item = WallpaperItem(path=str(p), media_type="video", name=p.stem)
                    mode = "muted" if self.video_mute else f"volume {self.video_volume}%"
                    return f"{label} ({mode})"
                errors.append(f"{label}: exit {proc.returncode}")
            except Exception as exc:
                errors.append(f"xwinwrap: {exc}")
        self._cleanup_video_ipc()
        raise RuntimeError("Video wallpaper could not be started. " + " | ".join(errors))

    def set_application(self, path: str) -> str:
        self._debug(f"set_application requested path={path!r}")
        self.stop_video()
        time.sleep(0.55)
        p = Path(path).resolve()
        if not p.exists():
            raise RuntimeError("Application file not found.")
        if p.suffix.lower() != ".exe":
            raise RuntimeError("Only Windows .exe application wallpapers are supported right now.")
        wine_bin = shutil.which("wine") or shutil.which("wine64")
        if not wine_bin:
            raise RuntimeError("Wine was not found. Please install wine to use application wallpapers.")

        env = os.environ.copy()
        env.setdefault("WINEDEBUG", "-all")
        env.setdefault("WINEDLLOVERRIDES", "winemenubuilder.exe=d")
        prefix_dir = self._application_prefix_dir()
        runtime_info = self.get_application_runtime_info()
        if not runtime_info.get("runtime_initialized"):
            self.initialize_application_runtime(force_reset=False)
        prefix_dir.mkdir(parents=True, exist_ok=True)
        env["WINEPREFIX"] = str(prefix_dir)
        before_ids = {w.get('id') for w in self._list_x11_windows() if w.get('id')}
        token = self._app_launch_token
        x, y, width, height = self._primary_monitor_bounds()
        cmd = [wine_bin, str(p)]
        self._debug(f"set_application start path={str(p)!r} prefix={str(prefix_dir)!r} before_windows={len(before_ids)} desktop_bounds={(x, y, width, height)}")
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(p.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
                env=env,
            )
            time.sleep(0.45)
            if proc.poll() is None:
                self.app_proc = proc
                self.app_wine_prefix = str(prefix_dir)
                self.video_paused = False
                self.current_item = WallpaperItem(path=str(p), media_type='application', name=p.stem)
                self._debug(f"set_application spawned pid={proc.pid} exe={p.name!r}")
                threading.Thread(
                    target=self._watch_application_window,
                    args=(proc, p, before_ids, token),
                    daemon=True,
                ).start()
                return 'wine desktop-window (experimental)'
            raise RuntimeError(f"wine: exit {proc.returncode}")
        except Exception as exc:
            raise RuntimeError("Application wallpaper could not be started. " + str(exc))


    def set_html(self, path: str) -> str:
        self._debug(f"set_html requested path={path!r}")
        self.stop_video()
        self._cleanup_generated_wallpaper()
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
        if item.media_type == "application":
            return self.set_application(item.path)
        raise RuntimeError("Unsupported media type.")
