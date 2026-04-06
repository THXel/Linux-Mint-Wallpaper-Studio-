Release build: 1.0.0

# Mint Wallpaper Studio

A modular Python wallpaper manager for Linux Mint Cinnamon/X11.

## Supported
- Local image wallpapers
- Local video wallpapers
- Wallpaper Engine workshop items that contain directly usable image or video files

## Not supported as live wallpapers
- Wallpaper Engine **Scene** wallpapers
- Wallpaper Engine **Application** wallpapers
- Wallpaper Engine **Web/HTML** wallpapers

## Features
- Tabs for All / Pictures / Videos / Wallpaper Engine
- Playlist enable/disable per item
- Random switching timer
- Local library and Wallpaper Engine sync library
- Multi-monitor playlist target selection with sync mode
- Thumbnail preview for videos with click-to-preview popup player
- Preview panel with file details
- Scene Inspector for unsupported item inspection
- Video wallpaper audio settings with volume slider and mute
- Add Media window with file/folder import and drag & drop support when `tkinterdnd2` is available

## Recommended install (Linux Mint / Ubuntu)

Install system packages:

```bash
sudo apt install python3-full python3-tk mpv ffmpeg ffmpegthumbnailer
```

Start the app with the bundled launcher:

```bash
chmod +x run.sh
./run.sh
```

The launcher will:
- create a local `.venv`
- install Python dependencies from `requirements.txt`
- start the app

## Manual install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Notes
- `xwinwrap` and `mpv` are required for video wallpapers.
- `python3-tk` is required for the Tk interface.
- `ffmpegthumbnailer` or `ffmpeg` is used for video thumbnails.
- `tkinterdnd2` enables drag & drop in the Add Media window.
- Unsupported Wallpaper Engine item types can be hidden during sync.

## Run

```bash
./run.sh
```
