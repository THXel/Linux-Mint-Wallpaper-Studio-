
#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
try:
    gi.require_version("GdkX11", "3.0")
except Exception:
    pass
from gi.repository import Gtk, WebKit2, GLib, Gdk
try:
    from gi.repository import GdkX11
except Exception:
    GdkX11 = None

LOG_PATH = Path('/tmp/mint_wallpaper_studio_html.log')


def log(msg: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open('a', encoding='utf-8') as fh:
            fh.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _project_default_properties(html_path: Path) -> dict:
    project = html_path.with_name("project.json")
    data = {}

    def _default_for(meta: dict):
        kind = str((meta or {}).get("type") or "").lower()
        if "value" in (meta or {}):
            return meta.get("value")
        if kind == "file":
            return ""
        if kind == "bool":
            return False
        if kind == "color":
            return "0 0 0"
        if kind in {"slider", "number", "integer"}:
            return meta.get("min", 0)
        if kind == "combo":
            options = meta.get("options") or []
            if isinstance(options, list) and options:
                first = options[0]
                if isinstance(first, dict):
                    return first.get("value") or first.get("label") or ""
                return first
            return ""
        if kind in {"text", "string"}:
            return ""
        return None

    try:
        if project.exists():
            raw = json.loads(project.read_text(encoding="utf-8", errors="ignore"))
            props = (((raw or {}).get("general") or {}).get("properties") or {})
            for key, meta in props.items():
                if not isinstance(meta, dict):
                    continue
                data[key] = {"value": _default_for(meta)}
    except Exception as exc:
        log(f'project.json parse failed: {exc}')
    return data


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        log('http: ' + (format % args))


def _start_http_server(base_dir: Path):
    server = ThreadingHTTPServer(('127.0.0.1', 0), lambda *a, **kw: QuietHandler(*a, directory=str(base_dir), **kw))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _build_bridge_script(default_props: dict) -> str:
    props_json = json.dumps(default_props, ensure_ascii=False)
    return f"""
(function() {{
  if (window.__mwsBridgeInstalled) return;
  window.__mwsBridgeInstalled = true;
  function mwslog() {{
    try {{
      var parts = Array.prototype.slice.call(arguments).map(function(x) {{
        try {{ return typeof x === 'string' ? x : JSON.stringify(x); }} catch (e) {{ return String(x); }}
      }});
      window.webkit.messageHandlers.mwslog.postMessage(parts.join(' '));
    }} catch (e) {{}}
  }}
  window.__mwslog = mwslog;
  window.onerror = function(msg, src, line, col, err) {{
    mwslog('window.onerror', String(msg), String(src || ''), String(line || ''), String(col || ''), err && err.stack ? err.stack : '');
  }};
  window.onunhandledrejection = function(e) {{
    var reason = e && e.reason ? (e.reason.stack || e.reason.message || String(e.reason)) : 'unknown';
    mwslog('unhandledrejection', reason);
  }};
  ['log','warn','error'].forEach(function(k) {{
    var orig = console[k];
    console[k] = function() {{
      try {{ mwslog('console.' + k, Array.prototype.slice.call(arguments).join(' ')); }} catch (e) {{}}
      try {{ return orig && orig.apply(console, arguments); }} catch (e) {{}}
    }};
  }});
  window.wallpaperRegisterAudioListener = window.wallpaperRegisterAudioListener || function() {{ mwslog('audio listener ignored'); }};
  window.wallpaperRegisterMediaStatusListener = window.wallpaperRegisterMediaStatusListener || function() {{ mwslog('media status listener ignored'); }};
  window.wallpaperPropertyListener = window.wallpaperPropertyListener || {{ applyUserProperties: function() {{}} }};
  window.__mwsDefaultProps = {props_json};
  mwslog('default props keys', Object.keys(window.__mwsDefaultProps || {{}}).join(','));
  document.addEventListener('DOMContentLoaded', function() {{ mwslog('domcontentloaded', location.href); }});
  window.addEventListener('load', function() {{ mwslog('window.load', location.href); }});
}})();
"""




def _get_xid(win):
    try:
        gdk_win = win.get_window()
        if gdk_win is None:
            return None
        if hasattr(gdk_win, "get_xid"):
            return int(gdk_win.get_xid())
        if GdkX11 is not None:
            return int(GdkX11.X11Window.get_xid(gdk_win))
    except Exception as exc:
        log(f'get_xid failed: {exc}')
    return None


def _apply_x11_desktop_hints(win):
    xid = _get_xid(win)
    if xid is None:
        return False
    hexid = hex(xid)
    cmds = [
        ["wmctrl", "-i", "-r", hexid, "-b", "add,below,sticky,skip_taskbar,skip_pager"],
        ["xprop", "-id", hexid, "-f", "_NET_WM_STATE", "32a", "-set", "_NET_WM_STATE",
         "_NET_WM_STATE_BELOW,_NET_WM_STATE_STICKY,_NET_WM_STATE_SKIP_TASKBAR,_NET_WM_STATE_SKIP_PAGER"],
        ["xprop", "-id", hexid, "-f", "_NET_WM_WINDOW_TYPE", "32a", "-set", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DESKTOP"],
    ]
    for cmd in cmds:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception as exc:
            log(f'x11 hint failed for {cmd[0]}: {exc}')
    try:
        gdk_win = win.get_window()
        if gdk_win is not None:
            gdk_win.lower()
    except Exception as exc:
        log(f'lower after x11 hints failed: {exc}')
    return False


def _screen_geometry():
    screen = Gdk.Screen.get_default()
    if screen is None:
        return 0, 0, 1920, 1080
    try:
        n = int(screen.get_n_monitors())
    except Exception:
        n = 0
    rects = []
    for i in range(max(0, n)):
        try:
            geo = screen.get_monitor_geometry(i)
            rects.append((int(geo.x), int(geo.y), int(geo.width), int(geo.height)))
        except Exception:
            pass
    if rects:
        min_x = min(r[0] for r in rects)
        min_y = min(r[1] for r in rects)
        max_x = max(r[0] + r[2] for r in rects)
        max_y = max(r[1] + r[3] for r in rects)
        width = max(1280, max_x - min_x)
        height = max(720, max_y - min_y)
        log(f'monitor bounds={rects} virtual={min_x},{min_y} {width}x{height}')
        return min_x, min_y, width, height
    try:
        return 0, 0, max(1280, screen.get_width()), max(720, screen.get_height())
    except Exception:
        return 0, 0, 1920, 1080



def _enable_click_through(win) -> bool:
    try:
        gdk_win = win.get_window()
        if gdk_win is None:
            log('click-through: no gdk window')
            return False
        try:
            gdk_win.set_pass_through(True)
            log('click-through: set_pass_through(True) applied')
            return True
        except Exception as exc:
            log(f'click-through: set_pass_through failed: {exc}')
        return False
    except Exception as exc:
        log(f'click-through: failed: {exc}')
        return False



def main() -> int:
    LOG_PATH.write_text('', encoding='utf-8')
    log('html desktop window runner starting')
    if len(sys.argv) < 2:
        log('missing target')
        return 2

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        log(f'html file missing: {p}')
        return 4

    x, y, width, height = _screen_geometry()
    try:
        screen = Gdk.Screen.get_default()
        primary = screen.get_primary_monitor() if screen is not None else -1
        log(f'primary_monitor={primary}')
    except Exception:
        pass
    default_props = _project_default_properties(p)
    log(f'target={p}')
    log(f'default_props={default_props}')

    server = _start_http_server(p.parent)
    uri = f"http://127.0.0.1:{server.server_port}/{quote(p.name)}"
    log(f'http uri={uri}')

    manager = WebKit2.UserContentManager()
    try:
        manager.register_script_message_handler('mwslog')
    except Exception:
        pass
    manager.add_script(WebKit2.UserScript.new(
        _build_bridge_script(default_props),
        WebKit2.UserContentInjectedFrames.ALL_FRAMES,
        WebKit2.UserScriptInjectionTime.START,
        None,
        None,
    ))

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("Mint Wallpaper Studio HTML Desktop")
    win.set_decorated(False)
    win.set_resizable(False)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_keep_below(True)
    win.stick()
    try:
        win.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
    except Exception as exc:
        log(f'type hint desktop failed: {exc}')
    try:
        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual() if screen is not None else None
        if visual is not None:
            win.set_visual(visual)
    except Exception as exc:
        log(f'visual setup failed: {exc}')

    web = WebKit2.WebView.new_with_user_content_manager(manager)
    web.set_hexpand(True)
    web.set_vexpand(True)
    settings = web.get_settings()
    settings.set_enable_javascript(True)
    settings.set_enable_webgl(True)
    try:
        settings.set_enable_accelerated_2d_canvas(False)
    except Exception:
        pass
    settings.set_allow_file_access_from_file_urls(True)
    settings.set_allow_universal_access_from_file_urls(True)
    settings.set_enable_developer_extras(True)
    settings.set_javascript_can_open_windows_automatically(True)
    try:
        settings.set_enable_write_console_messages_to_stdout(True)
    except Exception:
        pass
    try:
        web.set_background_color(Gdk.RGBA(0, 0, 0, 0))
    except Exception:
        pass

    overlay = Gtk.Overlay()
    overlay.set_hexpand(True)
    overlay.set_vexpand(True)
    overlay.add(web)
    win.add(overlay)

    def on_script_message(_mgr, js_result):
        try:
            value = js_result.get_js_value()
            if value.is_string():
                log('js: ' + value.to_string())
            else:
                log('js message received')
        except Exception as exc:
            log(f'js message parse failed: {exc}')

    try:
        manager.connect('script-message-received::mwslog', on_script_message)
    except Exception as exc:
        log(f'connect script message failed: {exc}')

    def on_load_failed(_web, event, failing_uri, error):
        log(f'load failed event={event} uri={failing_uri} error={getattr(error, "message", error)}')
        return False

    def on_process_terminated(_web, reason):
        log(f'web process terminated: {reason}')

    def on_load_changed(_web, event):
        log(f'load changed: {event.value_name if hasattr(event, "value_name") else event}')
        if event != WebKit2.LoadEvent.FINISHED:
            return
        props_json = json.dumps(default_props, ensure_ascii=False)
        js = f"""
        (function() {{
          try {{
            document.documentElement.style.width = '100vw';
            document.documentElement.style.height = '100vh';
            document.documentElement.style.margin = '0';
            document.documentElement.style.padding = '0';
            document.documentElement.style.overflow = 'hidden';
            if (document.body) {{
              document.body.style.margin = '0';
              document.body.style.padding = '0';
              document.body.style.overflow = 'hidden';
              document.body.style.minWidth = '100vw';
              document.body.style.minHeight = '100vh';
              document.body.style.width = '100vw';
              document.body.style.height = '100vh';
              document.body.style.background = 'transparent';
            }}
            var props = {props_json};
            function mwsApply() {{
              try {{ if (typeof init === 'function' && !window.__mwsInitDone) {{ window.__mwsInitDone = true; init(); }} }} catch (e) {{ __mwslog('init failed', e && e.stack ? e.stack : String(e)); }}
              try {{
                if (window.wallpaperPropertyListener && typeof window.wallpaperPropertyListener.applyUserProperties === 'function') {{
                  window.wallpaperPropertyListener.applyUserProperties(props);
                }}
              }} catch (e) {{ __mwslog('properties failed', e && e.stack ? e.stack : String(e)); }}
              try {{ if (typeof cl === 'function') {{ cl(); }} }} catch (e) {{ __mwslog('cl failed', e && e.stack ? e.stack : String(e)); }}
              try {{ window.dispatchEvent(new Event('resize')); }} catch (e) {{}}
              __mwslog('apply cycle finished');
            }}
            setTimeout(mwsApply, 25);
            setTimeout(mwsApply, 250);
            setTimeout(mwsApply, 1000);
          }} catch (e) {{ __mwslog('load hook failed', e && e.stack ? e.stack : String(e)); }}
        }})();
        """
        try:
            web.run_javascript(js, None, None, None)
        except Exception as exc:
            log(f'run_javascript failed: {exc}')


    def on_size_allocate(_widget, allocation):
        try:
            w = max(1, int(allocation.width))
            h = max(1, int(allocation.height))
            js = f"""
            (function() {{
              try {{
                window.dispatchEvent(new Event('resize'));
                if (document.body) {{
                  document.body.style.width = '{w}px';
                  document.body.style.height = '{h}px';
                }}
                var cvs = document.querySelectorAll('canvas');
                for (var i = 0; i < cvs.length; i++) {{
                  cvs[i].style.width = '{w}px';
                  cvs[i].style.height = '{h}px';
                }}
              }} catch (e) {{}}
            }})();
            """
            web.run_javascript(js, None, None, None)
        except Exception as exc:
            log(f'size allocate failed: {exc}')

    web.connect('size-allocate', on_size_allocate)
    web.connect('load-changed', on_load_changed)
    web.connect('load-failed', on_load_failed)
    try:
        web.connect('web-process-terminated', on_process_terminated)
    except Exception:
        pass

    def _lower_window():
        try:
            gx, gy, gw, gh = _screen_geometry()
            gdk_win = win.get_window()
            if gdk_win is not None:
                try:
                    gdk_win.move_resize(gx, gy, gw, gh)
                except Exception:
                    pass
                gdk_win.lower()
            try:
                win.move(gx, gy)
            except Exception:
                pass
            try:
                win.resize(gw, gh)
            except Exception:
                pass
        except Exception as exc:
            log(f'lower window failed: {exc}')
        return False

    def _refresh_desktop_state():
        try:
            _lower_window()
            _apply_x11_desktop_hints(win)
        except Exception as exc:
            log(f'refresh desktop state failed: {exc}')
        return True

    def place_window():
        try:
            gx, gy, gw, gh = _screen_geometry()
            win.set_default_size(gw, gh)
            try:
                win.move(gx, gy)
            except Exception:
                pass
            try:
                win.resize(gw, gh)
            except Exception:
                pass
            try:
                win.maximize()
            except Exception:
                pass
            try:
                win.fullscreen()
            except Exception:
                pass
            win.present()
            GLib.timeout_add(150, _lower_window)
            GLib.timeout_add(350, lambda: _apply_x11_desktop_hints(win))
            GLib.timeout_add(700, _lower_window)
            GLib.timeout_add(1200, lambda: _apply_x11_desktop_hints(win))
            GLib.timeout_add(1800, _lower_window)
            GLib.timeout_add_seconds(3, _refresh_desktop_state)
            log(f'desktop window placed at {gx},{gy} size {gw}x{gh}')
        except Exception as exc:
            log(f'place window failed: {exc}')
        return False

    def start_load():
        log('loading uri now')
        try:
            web.load_uri(uri)
        except Exception as exc:
            log(f'load_uri failed: {exc}')
            try:
                html = p.read_text(encoding='utf-8', errors='ignore')
                web.load_html(html, uri.rsplit('/', 1)[0] + '/')
            except Exception as exc2:
                log(f'load_html fallback failed: {exc2}')
                return False
        return False

    def cleanup(*_args):
        log('cleanup requested')
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        Gtk.main_quit()
        return False


    def on_map_event(*_args):
        GLib.timeout_add(80, lambda: _apply_x11_desktop_hints(win))
        GLib.timeout_add(250, _lower_window)
        return False

    win.connect('map-event', on_map_event)
    win.connect('delete-event', cleanup)
    win.connect('destroy', cleanup)

    def on_realize(_widget):
        try:
            _enable_click_through(win)
        except Exception as exc:
            log(f'on_realize click-through failed: {exc}')
        return None

    win.connect('realize', on_realize)
    win.show_all()
    GLib.idle_add(place_window)
    GLib.timeout_add(350, start_load)
    Gtk.main()
    cleanup()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
