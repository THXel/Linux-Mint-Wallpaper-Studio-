from __future__ import annotations
import json
from pathlib import Path
from typing import List, Tuple
from .models import WallpaperItem
from .utils import classify_media, scan_paths

WORKSHOP_APP_ID = "431960"  # Wallpaper Engine


def _collect_scene_info(folder: Path) -> tuple[list[str], dict]:
    files: list[str] = []
    props: dict = {}
    for child in sorted(folder.rglob("*")):
        if child.is_file():
            try:
                files.append(str(child.relative_to(folder)))
            except Exception:
                files.append(child.name)

    project_json = folder / "project.json"
    if project_json.exists():
        try:
            pdata = json.loads(project_json.read_text(encoding="utf-8", errors="ignore"))
            props["project_type"] = str(pdata.get("type", ""))
            props["title"] = str(pdata.get("title", ""))
            props["workshopid"] = str(pdata.get("workshopid", ""))
            tags = pdata.get("tags")
            if isinstance(tags, list):
                props["tags"] = tags[:20]
            gen = pdata.get("general", {})
            if isinstance(gen, dict):
                properties = gen.get("properties", {})
                if isinstance(properties, dict):
                    clean = {}
                    for key, meta in list(properties.items())[:40]:
                        if isinstance(meta, dict):
                            clean[key] = {
                                "text": str(meta.get("text", key)),
                                "type": str(meta.get("type", "")),
                                "value": meta.get("value"),
                            }
                    props["project_properties"] = clean
        except Exception:
            pass

    scene_json = folder / "scene.json"
    if scene_json.exists():
        try:
            sdata = json.loads(scene_json.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(sdata, dict):
                props["scene_top_keys"] = sorted(list(sdata.keys()))[:30]
        except Exception:
            pass

    return files[:150], props


def detect_steam_workshop_paths() -> List[Path]:
    home = Path.home()
    candidates = [
        home / ".local/share/Steam/steamapps/workshop/content" / WORKSHOP_APP_ID,
        home / ".steam/steam/steamapps/workshop/content" / WORKSHOP_APP_ID,
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/workshop/content" / WORKSHOP_APP_ID,
        home / ".var/app/com.valvesoftware.Steam/data/Steam/steamapps/workshop/content" / WORKSHOP_APP_ID,
    ]
    out = []
    seen = set()
    for p in candidates:
        if p.exists() and p not in seen:
            out.append(p)
            seen.add(p)
    return out




def detect_steam_install_type(roots: List[Path] | None = None) -> str:
    roots = roots or detect_steam_workshop_paths()
    kinds = []
    for p in roots:
        sp = str(p)
        if "/.var/app/com.valvesoftware.Steam/" in sp:
            kinds.append("Flatpak")
        else:
            kinds.append("System package")
    kinds = sorted(set(kinds))
    if not kinds:
        return "Steam workshop path not found"
    if len(kinds) == 2:
        return "Flatpak + System package"
    return kinds[0]


def _read_project_meta(folder: Path) -> tuple[str, str, str]:
    title = folder.name
    notes = ""
    ptype = ""
    pj = folder / "project.json"
    if pj.exists():
        try:
            data = json.loads(pj.read_text(encoding="utf-8", errors="ignore"))
            title = data.get("title") or data.get("workshoptitle") or title
            ptype = str(data.get("type") or "").strip()
            if ptype:
                notes = f"project:{ptype}"
        except Exception:
            pass
    return title, notes, ptype


def _pick_supported_file(folder: Path, project_type: str = "") -> tuple[Path | None, str]:
    preferred = []
    for child in folder.rglob("*"):
        if child.is_file():
            if child.name.lower().startswith("preview."):
                continue
            mt = classify_media(child)
            if mt:
                preferred.append((child, mt))
    if not preferred:
        return None, ""
    ptype = str(project_type).lower()
    # Prefer real videos for video projects, otherwise larger real media first
    preferred.sort(key=lambda x: (
        0 if (ptype == "video" and x[1] == "video") else 1,
        0 if x[1] == "video" else 1,
        -x[0].stat().st_size,
        len(x[0].parts),
        x[0].name.lower(),
    ))
    chosen, mt = preferred[0]
    return chosen, mt


def sync_wallpaper_engine(show_unsupported: bool = False) -> Tuple[List[WallpaperItem], List[Path]]:
    roots = detect_steam_workshop_paths()
    items: List[WallpaperItem] = []
    for root in roots:
        for folder in root.iterdir():
            if not folder.is_dir():
                continue
            title, notes, ptype = _read_project_meta(folder)
            preview = None
            for candidate in ("preview.gif", "preview.jpg", "preview.png", "preview.webp"):
                cp = folder / candidate
                if cp.exists():
                    preview = cp
                    break

            ptype_l = ptype.lower()
            if ptype_l in {"scene", "application"} and not show_unsupported:
                continue
            if ptype_l in {"scene", "application"}:
                # Keep item visible, but not directly playable
                p = preview if preview and preview.exists() else folder
                scene_files, scene_properties = _collect_scene_info(folder)
                item = WallpaperItem(
                    path=str(p), media_type="image" if preview else "video", name=title, source="wallpaper_engine",
                    format=(p.suffix.lower().lstrip(".") if isinstance(p, Path) and p.is_file() else "folder"),
                    folder=str(folder), workshop_id=folder.name, supported=False,
                    notes=(notes + " preview-only").strip(),
                    scene_files=scene_files, scene_properties=scene_properties,
                )
                if preview and preview.exists():
                    st = preview.stat()
                    item.size = st.st_size
                    item.modified_ts = st.st_mtime
                items.append(item)
                continue

            if ptype_l == "web":
                index_html = folder / "index.html"
                if index_html.exists():
                    item = WallpaperItem.from_path(index_html, "html", source="wallpaper_engine", workshop_id=folder.name, notes=notes)
                    item.name = title
                    item.folder = str(folder)
                    items.append(item)
                    continue

            media_file, mt = _pick_supported_file(folder, ptype)
            if media_file is None:
                # fall back to preview only
                if preview and preview.exists():
                    item = WallpaperItem.from_path(preview, "image", source="wallpaper_engine", workshop_id=folder.name, notes=(notes + " preview-only").strip())
                    item.name = title
                    item.supported = False
                    item.scene_files, item.scene_properties = _collect_scene_info(folder)
                    items.append(item)
                else:
                    item = WallpaperItem(
                        path=str(folder), media_type="video", name=title, source="wallpaper_engine",
                        format="folder", folder=str(folder), workshop_id=folder.name, supported=False,
                        notes=(notes + " unsupported").strip(),
                    )
                    items.append(item)
                continue

            item = WallpaperItem.from_path(media_file, mt, source="wallpaper_engine", workshop_id=folder.name, notes=notes)
            item.name = title
            items.append(item)
    items.sort(key=lambda i: (i.source, i.name.lower()))
    return items, roots
