<p align="center">
  <img src="https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Mint%20Wallpaper%20Studio%20Logo.png" width="900" alt="Mint Wallpaper Studio Banner">
</p>

<h1 align="center">🟢 Mint Wallpaper Studio</h1>

<p align="center">
  A wallpaper manager for <b>Linux Mint</b> with support for images, videos, playlists, Wallpaper Engine import, HTML wallpapers, Scene wallpapers, and experimental application wallpapers.
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#screenshots">Screenshots</a> •
  <a href="#install">Install</a> •
  <a href="#features">Features</a> •
  <a href="#wallpaper-engine">Wallpaper Engine</a> •
  <a href="#notes">Notes</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Linux-Mint-87CF3E?style=for-the-badge&logo=linuxmint&logoColor=white" alt="Linux Mint">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Version-1.2.0-green?style=for-the-badge" alt="Version 1.2.0">
  <img src="https://img.shields.io/badge/Status-unstable-orange?style=for-the-badge" alt=Unstable">
</p>

---

## Overview

**Mint Wallpaper Studio** is a wallpaper manager built for **Linux Mint** with a focus on a clean workflow and practical support for both static and animated wallpapers.

It supports:

- 🖼️ image wallpapers
- 🎥 video wallpapers
- 🌐 HTML wallpapers
- 🎬 Wallpaper Engine Scene wallpapers
- 🧪 experimental application wallpapers
- 📂 playlists
- 🎲 auto change
- 🖥️ multi-monitor modes
- 🔊 per-monitor audio control
- ⏸️ fullscreen pause / resume
- 🔄 Wallpaper Engine workshop import
- 🧺 tray integration

**Recommended environment:** **Linux Mint / Cinnamon / X11**

---

## Features

### Main features

- Local image and video wallpapers
- HTML wallpapers
- Wallpaper Engine Scene support
- Experimental application wallpapers
- Wallpaper Engine import for compatible workshop items
- Playlists and random / automatic changing
- Multi-monitor support
- Per-monitor audio control
- Fullscreen auto-pause
- Tray integration

### Monitor modes

- **Same on all monitors**
- **Different per monitor**
- **Stretch across monitors**

---

## Screenshots

### Main UI
![UI Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/UI_Screenshot.png)

### Options
![Options Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Option_Screenshot.png)

### Wallpaper Engine Sync
![Wallpaper Engine Sync Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/WallpaerEngineSync_Screenshot.png)

---

## Install

Download the latest package from the GitHub Releases page:

**GitHub Releases:**  
https://github.com/THXel/Linux-Mint-Wallpaper-Studio-/releases

### Install package

```bash
cd ~/Downloads
sudo apt install ./mint-wallpaper-studio_0.8.0.deb
```

If needed:

```bash
sudo dpkg -i mint-wallpaper-studio_0.8.0.deb
sudo apt -f install
```

### Start

```bash
mint-wallpaper-studio
```

### Remove

```bash
sudo apt remove mint-wallpaper-studio
```

---

## Wallpaper Engine

Mint Wallpaper Studio can import **compatible Wallpaper Engine workshop items**.

Supported or partially supported content includes:

- image wallpapers
- video wallpapers
- Scene wallpapers
- some HTML wallpapers
- some application wallpapers

### Scene support

Wallpaper Engine **Scenes** are supported through `linux-wallpaperengine`.

This includes:

- Scene detection during sync
- Scene import into the library
- backend detection inside the app
- in-app installation support for `linux-wallpaperengine`
- automatic X11 / XRandR monitor detection

Scene wallpapers currently work in:

- **Same on all monitors**
- **Different per monitor**

When **Stretch across monitors** is active and Auto Change selects a Scene wallpaper, the app temporarily falls back to **Same on all monitors** for that Scene.

---

## Dependencies

The package may require common runtime tools such as:

- `python3`
- `python3-tk`
- `python3-pil`
- `python3-pystray`
- `python3-gi`
- `mpv`
- `wmctrl`
- `xwallpaper`
- `xdotool`
- `libnotify-bin`
- `gir1.2-ayatanaappindicator3-0.1`
- `gir1.2-webkit2-4.1`

Optional for application wallpapers:

- `wine`
- `winetricks`

### External projects

Mint Wallpaper Studio integrates with or depends on external projects such as:

- [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine)
- [mpv](https://mpv.io/)

---

## Notes

- **Application wallpapers are experimental**
- **Applications are currently primary-monitor only**
- **HTML wallpapers currently work best with Stretch across monitors**
- **Scene wallpapers do not use true Stretch across monitors**
- Some Wallpaper Engine items may still be limited by Linux, X11, Wine, or desktop environment behavior

---

## Troubleshooting

### A wallpaper does not play

Check that the required playback tools are installed and that the wallpaper type is supported.

### A Wallpaper Engine item imports but does not work correctly

Some workshop items depend on unsupported Scene behavior, complex HTML logic, application runtimes, or Wine compatibility.

### The tray icon is missing

Install appindicator support:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

### Multi-monitor behavior is not what you expect

Check:

- selected monitor mode
- playlist target
- auto change settings
- wallpaper type limitations
- your X11 / Cinnamon monitor layout

### A Scene wallpaper does not start

Make sure `linux-wallpaperengine` is installed and available.

---

## Issues / Feedback

If you report a bug, please include:

- Linux Mint version
- desktop environment
- whether you use Cinnamon / X11
- app version
- wallpaper type
- steps to reproduce
- screenshots or logs

---

## License

This project is licensed under the MIT License. See the [LICENSE.MD](LICENSE.MD) file for details.

---

## Author

Created by **THXel**
