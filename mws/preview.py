from __future__ import annotations
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image, ImageOps, ImageDraw
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
    Image = ImageOps = ImageDraw = None


def image_resolution(path: Path) -> tuple[int, int]:
    if PIL_AVAILABLE:
        try:
            with Image.open(path) as im:
                return im.size
        except Exception:
            pass
    return (0, 0)


def _fit_to_canvas(im: "Image.Image", max_size: Tuple[int, int]) -> "Image.Image":
    im = ImageOps.exif_transpose(im)
    im.thumbnail(max_size)
    canvas = Image.new("RGB", max_size, (8, 16, 32))
    x = (max_size[0] - im.width) // 2
    y = (max_size[1] - im.height) // 2
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    canvas.paste(im.convert("RGB"), (x, y))
    return canvas


def render_image_preview(path: Path, max_size: Tuple[int, int]) -> Optional["Image.Image"]:
    if not PIL_AVAILABLE:
        return None
    try:
        with Image.open(path) as im:
            return _fit_to_canvas(im, max_size)
    except Exception:
        return None


def _draw_video_placeholder(max_size: Tuple[int, int], text: str = "Video") -> Optional["Image.Image"]:
    if not PIL_AVAILABLE:
        return None
    img = Image.new("RGB", max_size, (8, 16, 32))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((20, 20, max_size[0]-20, max_size[1]-20), radius=18, outline=(70, 100, 140), width=2)
    d.polygon([(max_size[0]//2 - 20, max_size[1]//2 - 28), (max_size[0]//2 - 20, max_size[1]//2 + 28), (max_size[0]//2 + 30, max_size[1]//2)], fill=(105, 167, 255))
    d.text((24, max_size[1]-42), text, fill=(210, 225, 245))
    return img


def _load_thumb(tmp: Path, max_size: Tuple[int, int]) -> Optional["Image.Image"]:
    if tmp.exists() and tmp.stat().st_size > 0:
        try:
            return render_image_preview(tmp, max_size)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    return None


def render_video_thumbnail(path: Path, max_size: Tuple[int, int]) -> Optional["Image.Image"]:
    if not PIL_AVAILABLE:
        return None
    try:
        with tempfile.NamedTemporaryFile(prefix="mws_", suffix=".jpg", delete=False) as fh:
            tmp = Path(fh.name)
        if shutil.which("ffmpegthumbnailer"):
            for size in (max_size[0], max(256, max_size[0] // 2)):
                subprocess.run([
                    "ffmpegthumbnailer", "-i", str(path), "-o", str(tmp), "-s", str(size), "-f"
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                thumb = _load_thumb(tmp, max_size)
                if thumb is not None:
                    return thumb
        if shutil.which("ffmpeg"):
            for ts in ("00:00:00.100", "00:00:01.000", "00:00:02.000"):
                subprocess.run([
                    "ffmpeg", "-y", "-ss", ts, "-i", str(path), "-frames:v", "1", "-vf", f"scale={max_size[0]}:-1", str(tmp)
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                thumb = _load_thumb(tmp, max_size)
                if thumb is not None:
                    return thumb
    except Exception:
        pass
    return _draw_video_placeholder(max_size, path.suffix.upper().lstrip('.') or "Video")


def render_image_preview_file(path: Path, max_size: Tuple[int, int]) -> Optional[Path]:
    """Return a temporary PNG path for image previews even without PIL."""
    try:
        if PIL_AVAILABLE:
            img = render_image_preview(path, max_size)
            if img is not None:
                tmp = Path(tempfile.mkstemp(prefix="mws_img_", suffix=".png")[1])
                img.save(tmp, format="PNG")
                return tmp
    except Exception:
        pass

    # Native Tk fallback works for PNG/GIF/PPM/PGM on most Linux installs.
    if path.suffix.lower() in {'.png', '.gif', '.ppm', '.pgm'}:
        return path

    # ffmpeg/convert fallback to PNG thumbnail
    out = Path(tempfile.mkstemp(prefix="mws_img_", suffix=".png")[1])
    try:
        if shutil.which('ffmpeg'):
            subprocess.run([
                'ffmpeg', '-y', '-i', str(path), '-vf', f'scale={max_size[0]}:-1:force_original_aspect_ratio=decrease',
                '-frames:v', '1', str(out)
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            if out.exists() and out.stat().st_size > 0:
                return out
        if shutil.which('convert'):
            subprocess.run([
                'convert', str(path), '-auto-orient', '-thumbnail', f'{max_size[0]}x{max_size[1]}>', str(out)
            ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            if out.exists() and out.stat().st_size > 0:
                return out
    except Exception:
        pass
    try:
        out.unlink(missing_ok=True)
    except Exception:
        pass
    return None


def render_video_thumbnail_file(path: Path, max_size: Tuple[int, int]) -> Optional[Path]:
    """Return a temporary PNG path for video thumbnails, with PIL optional."""
    out = Path(tempfile.mkstemp(prefix='mws_vid_', suffix='.png')[1])
    try:
        if shutil.which('ffmpegthumbnailer'):
            for size in (max_size[0], max(256, max_size[0] // 2)):
                subprocess.run([
                    'ffmpegthumbnailer', '-i', str(path), '-o', str(out), '-s', str(size), '-f'
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
                if out.exists() and out.stat().st_size > 0:
                    return out
        if shutil.which('ffmpeg'):
            for ts in ('00:00:00.300', '00:00:01.000', '00:00:02.000', '00:00:03.000'):
                subprocess.run([
                    'ffmpeg', '-y', '-ss', ts, '-i', str(path), '-frames:v', '1',
                    '-vf', f'scale={max_size[0]}:-1:force_original_aspect_ratio=decrease', str(out)
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                if out.exists() and out.stat().st_size > 0:
                    return out
    except Exception:
        pass
    try:
        out.unlink(missing_ok=True)
    except Exception:
        pass
    return None


def _draw_html_placeholder(max_size: Tuple[int, int], text: str = "HTML") -> Optional["Image.Image"]:
    if not PIL_AVAILABLE:
        return None
    img = Image.new("RGB", max_size, (8, 16, 32))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((20, 20, max_size[0]-20, max_size[1]-20), radius=18, outline=(70, 140, 120), width=2)
    d.text((28, 28), "HTML Wallpaper", fill=(170, 245, 220))
    d.text((28, max_size[1]-42), text[:32], fill=(210, 225, 245))
    return img

def render_html_preview(path: Path, max_size: Tuple[int, int]) -> Optional["Image.Image"]:
    folder = path.parent if path.is_file() else path
    candidates = []
    stem = path.stem if path.is_file() else ""
    if stem:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidates.append(folder / f"{stem}{ext}")
    for name in ("preview.jpg", "preview.png", "preview.webp", "thumbnail.jpg", "thumbnail.png"):
        candidates.append(folder / name)
    for candidate in candidates:
        if candidate.exists():
            return render_image_preview(candidate, max_size)
    return _draw_html_placeholder(max_size, path.stem or "HTML")

def render_html_preview_file(path: Path, max_size: Tuple[int, int]) -> Optional[Path]:
    try:
        img = render_html_preview(path, max_size)
        if img is not None:
            tmp = Path(tempfile.mkstemp(prefix="mws_html_", suffix=".png")[1])
            img.save(tmp, format="PNG")
            return tmp
    except Exception:
        pass
    return None



def find_html_preview_image(path: Path) -> Optional[Path]:
    folder = path.parent if path.is_file() else path
    candidates = [
        folder / 'preview.jpg',
        folder / 'preview.png',
        folder / 'preview.webp',
        folder / 'preview.jpeg',
        folder / 'thumbnail.jpg',
        folder / 'thumbnail.png',
        folder / f"{path.stem}.jpg",
        folder / f"{path.stem}.png",
        folder / f"{path.stem}.webp",
        folder / f"{path.stem}.jpeg",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand
    return None
