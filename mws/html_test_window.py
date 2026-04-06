#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, WebKit2, GLib, Gdk

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
                val = _default_for(meta)
                data[key] = {"value": val}
    except Exception as exc:
        log(f'project.json parse failed: {exc}')
    return data


def _screen_size() -> tuple[int, int]:
    try:
        screen = Gdk.Screen.get_default()
        if screen is not None:
            return max(1280, screen.get_width()), max(720, screen.get_height())
    except Exception:
        pass
    return 1920, 1080


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        log('http: ' + (format % args))


def _start_http_server(base_dir: Path):
    server = ThreadingHTTPServer(('127.0.0.1', 0), lambda *a, **kw: QuietHandler(*a, directory=str(base_dir), **kw))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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


def main() -> int:
    LOG_PATH.write_text('', encoding='utf-8')
    log('html internal test runner starting')
    if len(sys.argv) < 2:
        log('test window missing target')
        return 2

    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        log(f'html file missing: {p}')
        return 4

    width, height = _screen_size()
    default_props = _project_default_properties(p)
    log(f'target={p}')
    log(f'default_props={default_props}')

    server, _thread = _start_http_server(p.parent)
    uri = f"http://127.0.0.1:{server.server_port}/{quote(p.name)}"
    log(f'http uri={uri}')

    manager = WebKit2.UserContentManager()
    try:
        manager.register_script_message_handler('mwslog')
    except Exception:
        pass
    script = WebKit2.UserScript.new(
        _build_bridge_script(default_props),
        WebKit2.UserContentInjectedFrames.ALL_FRAMES,
        WebKit2.UserScriptInjectionTime.START,
        None,
        None,
    )
    manager.add_script(script)

    plug = Gtk.Window(title='Mint Wallpaper Studio HTML Internal Test')
    plug.set_app_paintable(True)
    plug.set_default_size(width, height)
    try:
        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual() if screen is not None else None
        if visual is not None:
            plug.set_visual(visual)
    except Exception as exc:
        log(f'test visual setup failed: {exc}')

    web = WebKit2.WebView.new_with_user_content_manager(manager)
    web.set_size_request(width, height)
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

    web.connect('load-changed', on_load_changed)
    web.connect('load-failed', on_load_failed)
    try:
        web.connect('web-process-terminated', on_process_terminated)
    except Exception:
        pass

    box = Gtk.Box()
    box.set_size_request(width, height)
    box.pack_start(web, True, True, 0)
    plug.add(box)
    plug.show_all()

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

    GLib.timeout_add(350, start_load)
    plug.connect('delete-event', cleanup)
    plug.connect('destroy', cleanup)
    Gtk.main()
    cleanup()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
