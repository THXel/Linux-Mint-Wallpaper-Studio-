<p align="center">
  <img src="https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Mint%20Wallpaper%20Studio%20Logo.png" width="900" alt="Linux Mint Wallpaper Studio Banner">
</p>

<h1 align="center">🟢 Linux Mint Wallpaper Studio</h1>

<p align="center">
  A modern wallpaper manager for <b>Linux Mint</b> with support for local image wallpapers, video wallpapers,
  playlists, preview tools, Wallpaper Engine workshop sync, and desktop integration.
</p>

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-table-of-contents">Table of Contents</a> •
  <a href="#-screenshots">Screenshots</a> •
  <a href="#-download">Download</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-dependencies--required-packages">Dependencies</a> •
  <a href="#-wallpaper-engine-tutorial">Wallpaper Engine Tutorial</a> •
  <a href="#-usage-guide">Usage</a> •
  <a href="#-troubleshooting">Troubleshooting</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Linux-Mint-87CF3E?style=for-the-badge&logo=linuxmint&logoColor=white" alt="Linux Mint">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Version-1.0.0-green?style=for-the-badge" alt="Version 1.0.0">
  <img src="https://img.shields.io/badge/Status-Release-brightgreen?style=for-the-badge" alt="Release">
</p>

---

## 📌 Overview

**Linux Mint Wallpaper Studio** is a wallpaper manager built for **Linux Mint** with a focus on a clean UI, simple workflow, and support for both static and animated wallpapers.

The app is designed to help you manage:

- 🖼️ local image wallpapers
- 🎥 local video wallpapers
- 📂 playlists
- 🎲 random wallpaper switching
- 👀 preview tools
- 🔄 Wallpaper Engine workshop sync for compatible items
- 🖥️ multi-monitor behavior
- 🔊 audio controls for video wallpapers
- ⏸️ fullscreen pause behavior
- 🌐 desktop HTML mode support

It aims to make animated wallpapers on Linux Mint easier to use without needing a complicated setup.

---

## 📚 Table of Contents

- [📌 Overview](#-overview)
- [✨ Main Features](#-main-features)
- [🖼️ Screenshots](#️-screenshots)
- [📥 Download](#-download)
- [📦 Installation](#-installation)
- [🧩 Dependencies / Required Packages](#-dependencies--required-packages)
- [🐍 Python / Runtime Notes](#-python--runtime-notes)
- [⚡ Optional One-Line Install Command](#-optional-one-line-install-command)
- [🎮 Wallpaper Engine Tutorial](#-wallpaper-engine-tutorial)
- [🧠 Supported Wallpaper Types](#-supported-wallpaper-types)
- [🚫 Unsupported Wallpaper Types](#-unsupported-wallpaper-types)
- [🧭 Usage Guide](#-usage-guide)
- [🛠️ Feature Breakdown](#️-feature-breakdown)
- [⚠️ Known Limitations](#️-known-limitations)
- [🧯 Troubleshooting](#-troubleshooting)
- [🚧 Project Status](#-project-status)
- [🤝 Contributing](#-contributing)
- [🐞 Issues and Feedback](#-issues-and-feedback)
- [📜 License](#-license)
- [👑 Author](#-author)

---

## ✨ Main Features

Linux Mint Wallpaper Studio includes the following core features:

- 🖼️ **Local image wallpapers**
- 🎥 **Local video wallpapers**
- 🔄 **Wallpaper Engine sync** for compatible workshop items
- 📂 **Playlist management**
- 🎲 **Random wallpaper switching** with timer support
- 👀 **Preview panel** with file details
- 🧩 **Thumbnail previews** for video files
- ▶️ **Click-to-preview popup player**
- 🖥️ **Multi-monitor playlist target selection**
- 🔁 **Sync mode support** for monitors
- 🔊 **Audio controls** including mute and volume slider
- ➕ **Add Media window** for files and folders
- 🖱️ **Drag & drop support** when `tkinterdnd2` is available
- 🔍 **Scene Inspector** for unsupported Wallpaper Engine items
- 🌐 **Desktop HTML mode**
- ⏸️ **Fullscreen pause support**
- 🧺 **Tray integration**
- 🪟 **Improved multi-instance handling**

---

## 🖼️ Screenshots

### 🧠 Main UI

The main library window shows your wallpapers, preview area, controls, playlists, and media management tools.

![UI Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/UI_Screenshot.png)

---

### ⚙️ Options

The options window contains important settings for startup behavior, playback behavior, syncing, fullscreen pause handling, tray behavior, and other app preferences.

![Options Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Option_Screenshot.png)

---

### 🔄 Wallpaper Engine Sync Window

The sync window helps you browse compatible workshop content and import supported wallpapers into the application.

![Wallpaper Engine Sync Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/WallpaerEngineSync_Screenshot.png)

---

### 🔍 Wallpaper Engine Search Example

This screenshot shows the kind of content you should look for before syncing.

![Wallpaper Engine Search Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Wallpaper_Engine_Screenshot_1.png)

---

### 🎛️ Wallpaper Engine Filter Example

This screenshot shows useful filter settings when searching for compatible content.

![Wallpaper Engine Filter Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Wallpaper_Engine_Screenshot_2.png)

---

## 📥 Download

### Recommended release file

Download the current release package:

```text
mint-wallpaper-studio_1.0.0_all_release.deb
```

### Where to download it

The recommended place to download the release is the **GitHub repository / releases section** of this project.

You can place the downloaded `.deb` file in your `Downloads` folder and install it from there.

Example expected filename:

```text
mint-wallpaper-studio_1.0.0_all_release.deb
```

---

## 📦 Installation

### 1) Download the `.deb` file

Download:

```text
mint-wallpaper-studio_1.0.0_all_release.deb
```

and save it somewhere easy to access, for example:

```text
~/Downloads
```

---

### 2) Install the package

Open a terminal and run:

```bash
cd ~/Downloads
sudo dpkg -i mint-wallpaper-studio_1.0.0_all_release.deb
sudo apt -f install
```

This installs the package and then lets APT resolve any missing dependencies automatically.

---

### 3) Start the application

You can launch the app from the Linux Mint application menu, or start it manually with:

```bash
mint-wallpaper-studio
```

---

### 4) If you update from an older version

Just install the newer `.deb` package over the existing version:

```bash
cd ~/Downloads
sudo dpkg -i mint-wallpaper-studio_1.0.0_all_release.deb
sudo apt -f install
```

---

## 🧩 Dependencies / Required Packages

The release package depends on the following system packages:

- `python3`
- `python3-tk`
- `python3-pil`
- `python3-pystray`
- `python3-gi`
- `mpv`
- `x11-utils`
- `wmctrl`
- `gir1.2-ayatanaappindicator3-0.1`
- `libnotify-bin`
- `gir1.2-webkit2-4.1`

These are the required packages for the current release package and cover:

- the Python runtime
- the Tk GUI
- image handling
- system tray support
- GTK / GI bindings
- video playback
- X11 integration
- window control
- notifications
- embedded web / HTML components

---

## 🐍 Python / Runtime Notes

Linux Mint Wallpaper Studio is packaged as a `.deb`, so the recommended way to install it is through the package itself.

That means in normal use you usually **do not need to manually install Python modules with pip**.

The package relies on the Linux / Debian-style system packages listed above.

### What these packages are used for

- `python3` → Python runtime
- `python3-tk` → Tkinter GUI
- `python3-pil` → image processing / thumbnails
- `python3-pystray` → tray icon support
- `python3-gi` → GTK / GI integration
- `mpv` → video wallpaper playback
- `x11-utils` → X11 helper tools
- `wmctrl` → window management behavior
- `gir1.2-ayatanaappindicator3-0.1` → tray/appindicator integration
- `libnotify-bin` → desktop notifications
- `gir1.2-webkit2-4.1` → web / HTML integration

### Optional drag & drop note

Drag & drop support may use `tkinterdnd2` when available.

If your setup needs it manually, you can install it separately, but it is not part of the required `.deb` dependency list shown above.

---

## ⚡ Optional One-Line Install Command

If you want to install all required packages manually before installing the `.deb`, use:

```bash
sudo apt update && sudo apt install -y python3 python3-tk python3-pil python3-pystray python3-gi mpv x11-utils wmctrl gir1.2-ayatanaappindicator3-0.1 libnotify-bin gir1.2-webkit2-4.1
```

After that, install the release package:

```bash
cd ~/Downloads
sudo dpkg -i mint-wallpaper-studio_1.0.0_all_release.deb
```

If needed, finish with:

```bash
sudo apt -f install
```

---

## 🎮 Wallpaper Engine Tutorial

Linux Mint Wallpaper Studio can work with **Wallpaper Engine workshop items** when they contain directly usable media files such as **videos** or **images**.

Not every Wallpaper Engine item works the same way on Linux as it does on Windows.

---

### Step 1: Search for suitable wallpapers

Use Wallpaper Engine and search for wallpapers that are likely to contain:

- 🎥 video files
- 🖼️ image-based content
- simple directly playable media

Example screenshot:

![Wallpaper Engine Search](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Wallpaper_Engine_Screenshot_1.png)

### Good candidates usually are:

- video wallpapers
- animated backgrounds exported as video
- simple image-based wallpapers

### Bad candidates usually are:

- scene wallpapers with custom runtime rendering
- application-based wallpapers
- advanced web / HTML wallpapers

---

### Step 2: Use filters

Use Wallpaper Engine filters to narrow the results.

Example screenshot:

![Wallpaper Engine Filters](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Wallpaper_Engine_Screenshot_2.png)

### Recommended approach

✔️ Prefer:
- **Video**
- directly usable media content

⚠️ Optional:
- **Web** only if you want to inspect content, but it is not recommended as a guaranteed working live wallpaper type

❌ Avoid if you want the highest compatibility:
- **Scene**
- **Application**

---

### Step 3: Open Wallpaper Engine Sync in the app

Inside Linux Mint Wallpaper Studio:

1. Open the app
2. Open **Wallpaper Engine Sync**
3. Let the app scan workshop content
4. Select compatible wallpapers
5. Import them into your library

Example sync window:

![Wallpaper Engine Sync Window](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/WallpaerEngineSync_Screenshot.png)

---

### Step 4: Inspect unsupported items if needed

If a workshop item is not directly supported, the app can still detect it and show information about it through the **Scene Inspector**.

This is useful for understanding why a wallpaper may not work as a native live wallpaper on Linux Mint.

---

### Step 5: Preview before applying

Before setting a wallpaper live:

- use the preview panel
- use click-to-preview
- verify that the content plays correctly
- check that the monitor behavior is correct

This helps avoid importing unsupported or unsuitable content into active use.

---

## 🧠 Supported Wallpaper Types

### ✅ Supported

The following wallpaper types are supported:

- local image wallpapers
- local video wallpapers
- Wallpaper Engine workshop items that contain directly usable:
  - image files
  - video files

These are the most reliable content types for playback in Linux Mint Wallpaper Studio.

---

## 🚫 Unsupported Wallpaper Types

The following are currently **not supported as true native live wallpapers**:

- Wallpaper Engine **Scene** wallpapers
- Wallpaper Engine **Application** wallpapers
- Wallpaper Engine **Web / HTML** wallpapers as fully equivalent live wallpapers

### Important note

Some unsupported items may still be:

- detected
- listed
- inspected
- previewed in limited ways

but they are not guaranteed to behave like Windows Wallpaper Engine live wallpapers.

---

## 🧭 Usage Guide

### Typical workflow

1. **Add media**
   - import files
   - import folders
   - build a wallpaper library

2. **Preview content**
   - inspect the selected wallpaper
   - check file details
   - use popup preview

3. **Organize playlists**
   - group wallpapers
   - create themed sets
   - choose a target playlist

4. **Select monitor targets**
   - choose a display
   - assign playback behavior
   - use sync mode if needed

5. **Apply wallpaper**
   - start wallpaper playback
   - switch manually
   - or use random mode / playlist behavior

---

### Main launch methods

#### From the app menu
Open the Linux Mint menu and search for:

```text
Mint Wallpaper Studio
```

#### From terminal

```bash
mint-wallpaper-studio
```

---

## 🛠️ Feature Breakdown

### Library management
Store and manage wallpapers in one place.

### Image wallpapers
Use standard local image files as wallpapers.

### Video wallpapers
Use local video files as animated wallpapers.

### Playlists
Group wallpapers into playlists and organize playback.

### Random switching
Automatically switch wallpapers on a timer.

### Preview tools
Preview wallpapers before you apply them.

### Video thumbnails
See quick previews for video-based wallpapers.

### Popup preview player
Test wallpapers in a dedicated preview popup.

### Multi-monitor support
Control which screen should receive which wallpaper behavior.

### Sync mode
Mirror or coordinate wallpaper behavior across monitors.

### Audio controls
Mute or adjust volume for video wallpapers.

### Wallpaper Engine sync
Import compatible workshop items into your Linux Mint wallpaper library.

### Scene Inspector
Inspect unsupported items to understand their type and structure.

### Fullscreen pause
Pause wallpaper activity when fullscreen windows are active.

### Desktop HTML mode
Support for desktop-integrated HTML behavior where available.

### Tray integration
Control the app through the system tray.

---

## ⚠️ Known Limitations

- Scene wallpapers are not supported as native live wallpapers
- Application wallpapers are not supported
- Web / HTML wallpapers are not fully supported as native live wallpapers
- Linux desktop behavior can vary depending on:
  - X11
  - Cinnamon behavior
  - compositor setup
  - multi-monitor configuration
  - embedded desktop window behavior

---

## 🧯 Troubleshooting

### The wallpaper does not play
Check that:
- `mpv` is installed
- the file is supported
- the selected wallpaper is a direct image or video file
- your desktop/session supports the current playback method

### Wallpaper Engine item imports but does not work
This usually means the item is:
- a Scene wallpaper
- an Application wallpaper
- a Web / HTML wallpaper
- or otherwise not directly usable as a normal file-based wallpaper

### Tray icon is missing
Make sure the required appindicator-related package is installed:

```bash
gir1.2-ayatanaappindicator3-0.1
```

### HTML or web-based content does not behave like Wallpaper Engine on Windows
This is a platform limitation and depends heavily on Linux desktop integration and runtime behavior.

### Multi-monitor behavior is not what you expect
Check:
- playlist target selection
- sync mode settings
- active monitor configuration
- X11 desktop handling

---

## 🚧 Project Status

This project is actively developed and improved.

Current focus areas include:

- UI improvements
- better playlist handling
- improved preview workflow
- improved multi-instance handling
- expanded Wallpaper Engine compatibility where possible
- better Linux Mint integration

---

## 🤝 Contributing

Contributions, ideas, bug reports, and feedback are welcome.

You can help by:

- reporting bugs
- suggesting features
- testing on different Linux Mint setups
- improving compatibility
- improving stability
- helping refine Wallpaper Engine support behavior

---

## 🐞 Issues and Feedback

If something does not work correctly, please include as much detail as possible:

- Linux Mint version
- desktop environment
- whether you are using Cinnamon / X11
- installation method
- package version
- exact wallpaper type
- steps to reproduce
- screenshots
- terminal output
- whether the problem happens with local media, playlists, or Wallpaper Engine sync

---

## 📜 License

Add your preferred license here, for example:

- MIT
- GPL-3.0
- Apache-2.0

---

## 👑 Author

Created by **THXel**
