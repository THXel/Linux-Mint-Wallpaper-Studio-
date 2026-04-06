from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict


@dataclass
class WallpaperItem:
    path: str
    media_type: str  # image | video | html
    name: str
    source: str = "local"  # local | wallpaper_engine
    format: str = ""
    folder: str = ""
    size: int = 0
    width: int = 0
    height: int = 0
    modified_ts: float = 0.0
    workshop_id: str = ""
    supported: bool = True
    notes: str = ""
    enabled: bool = True
    scene_files: list[str] | None = None
    scene_properties: dict | None = None
    enabled_targets: dict | None = None
    playlist_order: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_path(cls, path: Path, media_type: str, source: str = "local", workshop_id: str = "", notes: str = "") -> "WallpaperItem":
        st = path.stat()
        return cls(
            path=str(path),
            media_type=media_type,
            name=path.stem,
            source=source,
            format=path.suffix.lower().lstrip('.'),
            folder=str(path.parent),
            size=st.st_size,
            modified_ts=st.st_mtime,
            workshop_id=workshop_id,
            notes=notes,
            enabled=True,
            playlist_order=0,
        )
