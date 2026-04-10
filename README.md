<p align="center">
  <img src="https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Mint%20Wallpaper%20Studio%20Logo.png" width="900" alt="Linux Mint Wallpaper Studio Banner">
</p>

<h1 align="center">🟢 Linux Mint Wallpaper Studio</h1>

<p align="center">
  A modern wallpaper manager for <b>Linux Mint</b> with support for image wallpapers, video wallpapers,
  playlists, Wallpaper Engine import, HTML wallpapers, experimental application wallpapers, and improved multi-monitor behavior.
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#screenshots">Screenshots</a> •
  <a href="#download">Download</a> •
  <a href="#installation">Installation</a> •
  <a href="#features">Features</a> •
  <a href="#wallpaper-engine">Wallpaper Engine</a> •
  <a href="#notes">Notes</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Linux-Mint-87CF3E?style=for-the-badge&logo=linuxmint&logoColor=white" alt="Linux Mint">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Version-1.1.0-green?style=for-the-badge" alt="Version 1.1.0">
  <img src="https://img.shields.io/badge/Status-Release-brightgreen?style=for-the-badge" alt="Release">
</p>

---

<a id="overview"></a>

## 📌 Overview

**Linux Mint Wallpaper Studio** is a wallpaper manager built for **Linux Mint**, focused on a clean UI, a practical workflow, and support for both static and animated wallpapers.

It is designed to make wallpapers on Linux Mint easier to manage without requiring a complicated setup.

Main supported content includes:

- 🖼️ local image wallpapers
- 🎥 local video wallpapers
- 🌐 HTML wallpapers
- 🧪 experimental application wallpapers
- 📂 playlists
- 🎲 automatic wallpaper changing
- 🔄 Wallpaper Engine workshop import for compatible items
- 🖥️ improved multi-monitor handling
- 🔊 per-monitor audio control
- ⏸️ fullscreen pause behavior
- 🧺 tray integration

---

## 📚 Table of Contents

- [📌 Overview](#overview)
- [✨ Main Features](#features)
- [🖼️ Screenshots](#screenshots)
- [📥 Download](#download)
- [📦 Installation](#installation)
- [🗑️ Deinstallation](#deinstallation)
- [🧩 Dependencies](#dependencies)
- [🎮 Wallpaper Engine](#wallpaper-engine)
- [🧠 Supported Wallpaper Types](#supported-wallpaper-types)
- [🚫 Unsupported / Limited Content](#unsupported)
- [🧭 Usage Guide](#usage-guide)
- [⚠️ Notes](#notes)
- [🧯 Troubleshooting](#troubleshooting)
- [🚧 Project Status](#project-status)
- [🤝 Contributing](#contributing)
- [🐞 Issues and Feedback](#issues-and-feedback)
- [📜 License](#license)
- [👑 Author](#author)

---

<a id="features"></a>

## ✨ Main Features

### Core features

- 🖼️ **Local image wallpapers**
- 🎥 **Local video wallpapers**
- 🌐 **HTML wallpapers**
- 🧪 **Experimental application wallpapers**
- 🔄 **Wallpaper Engine import** for compatible workshop items
- 📂 **Playlist management**
- 🎲 **Random wallpaper switching**
- 👀 **Preview panel** and click-to-preview tools
- 🖥️ **Multi-monitor support**
- 🔁 **Monitor modes**
  - **Same on all monitors**
  - **Different per monitor**
  - **Stretch across monitors**
- 🔊 **Per-monitor audio control**
- ⏸️ **Fullscreen auto-pause**
- 🧺 **Tray integration**
- ⚙️ **Managed Wine runtime tools** for application wallpapers

### What improved since v1.0.0

- much better multi-monitor logic
- cleaner monitor-aware UI behavior
- more reliable per-monitor auto change
- better video wallpaper handling
- improved fullscreen pause behavior
- better audio monitor selection and saving
- improved HTML wallpaper integration
- experimental application wallpaper workflow
- reworked settings window
- better tray behavior and background workflow

---

<a id="screenshots"></a>

## 🖼️ Screenshots

### 🧠 Main UI

![UI Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/UI_Screenshot.png)

---

### ⚙️ Options

![Options Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Option_Screenshot.png)

---

### 🔄 Wallpaper Engine Sync

![Wallpaper Engine Sync Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/WallpaerEngineSync_Screenshot.png)

---

### 🔍 Wallpaper Engine Search Example

![Wallpaper Engine Search Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Wallpaper_Engine_Screenshot_1.png)

---

### 🎛️ Wallpaper Engine Filter Example

![Wallpaper Engine Filter Screenshot](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Screenshots/Wallpaper_Engine_Screenshot_2.png)

---

<a id="download"></a>

## 📥 Download

### Recommended release file

Download the latest release package from the GitHub Releases page.

👉 **GitHub Releases:**  
https://github.com/THXel/Linux-Mint-Wallpaper-Studio-/releases

Recommended release filename:

```text
mint-wallpaper-studio_1.1.0.deb
```

---

<a id="installation"></a>

## 📦 Installation

### 1) Download the `.deb` file

Download the current release and save it somewhere easy to access, for example:

```text
~/Downloads
```

### 2) Install the package

```bash
cd ~/Downloads
sudo apt install ./mint-wallpaper-studio_1.1.0.deb
```

If needed, you can also use:

```bash
sudo dpkg -i mint-wallpaper-studio_1.1.0.deb
sudo apt -f install
```

### 3) Start the application

Start it from the Linux Mint application menu, or run:

```bash
mint-wallpaper-studio
```

### 4) Update from an older version

Install the newer `.deb` over the old one:

```bash
cd ~/Downloads
sudo apt install ./mint-wallpaper-studio_1.1.0.deb
```

---

<a id="deinstallation"></a>

## 🗑️ Deinstallation

### Standard removal

```bash
sudo apt remove mint-wallpaper-studio
```

### Full removal including config files

```bash
sudo apt purge mint-wallpaper-studio
```

### Remove no longer needed packages

```bash
sudo apt autoremove
```

---

<a id="dependencies"></a>

## 🧩 Dependencies

The release package depends on system packages required for:

- Python runtime
- Tk GUI
- image handling
- tray integration
- GTK / GI bindings
- video playback
- X11 utilities
- window management
- notifications
- embedded web / HTML support

Typical required packages include:

- `python3`
- `python3-tk`
- `python3-pil`
- `python3-pystray`
- `python3-gi`
- `mpv`
- `x11-utils`
- `wmctrl`
- `xwallpaper`
- `xdotool`
- `gir1.2-ayatanaappindicator3-0.1`
- `libnotify-bin`
- `gir1.2-webkit2-4.1`

Optional tools for application wallpapers:

- `wine`
- `winetricks`

---

<a id="wallpaper-engine"></a>

## 🎮 Wallpaper Engine

Linux Mint Wallpaper Studio can import **compatible Wallpaper Engine workshop items** when they contain directly usable media such as:

- 🎥 video files
- 🖼️ image files
- 🌐 some HTML-based content
- 🧪 some application-based content

### Recommended content types

Best results usually come from:

- **Video**
- **Image**
- simple directly usable media

### More limited content types

Some content types are only partially supported or experimental:

- **HTML / Web**
- **Application**

### Import workflow

1. Open **Wallpaper Engine Sync**
2. Scan workshop content
3. Review detected entries
4. Import supported wallpapers into the library
5. Preview them before applying

---

<a id="supported-wallpaper-types"></a>

## 🧠 Supported Wallpaper Types

### ✅ Supported

- local image wallpapers
- local video wallpapers
- compatible Wallpaper Engine image wallpapers
- compatible Wallpaper Engine video wallpapers
- HTML wallpapers
- experimental application wallpapers

---

<a id="unsupported"></a>

## 🚫 Unsupported / Limited Content

### Limited / experimental

- **HTML wallpapers**
  - currently intended for **Stretch across monitors**
- **Application wallpapers**
  - currently **experimental**
  - currently focused on **Primary monitor only**

### Not guaranteed

Some Wallpaper Engine items may still not behave like Windows Wallpaper Engine live wallpapers, especially when they rely on:

- custom scene rendering
- complex runtime logic
- engine-specific behavior
- Wine compatibility limits
- Linux desktop / X11 limitations

---

<a id="usage-guide"></a>

## 🧭 Usage Guide

### Typical workflow

1. **Add media**
   - import files or folders
2. **Preview content**
   - check images, videos, HTML, or app-based content
3. **Organize playlists**
   - build sets for different moods or monitors
4. **Choose monitor behavior**
   - Same on all monitors
   - Different per monitor
   - Stretch across monitors
5. **Apply wallpaper**
   - manually
   - randomly
   - or through auto change

### Auto Change

Auto Change supports:

- one shared rule for all monitors
- separate rules for each monitor when using **Different per monitor**

This works much better now together with monitor mode and playlist behavior.

### Application wallpapers

The **Applications** section includes:

- managed Wine runtime initialization
- reset tools
- Winetricks shortcut
- winecfg shortcut
- prefix folder tools

---

<a id="notes"></a>

## ⚠️ Notes

- **Application wallpapers are experimental**
- **HTML wallpapers are currently intended for Stretch across monitors**
- **Application wallpapers are currently intended for the Primary monitor workflow**
- best results are currently expected on:
  - **Linux Mint**
  - **Cinnamon**
  - **X11**

Multi-monitor behavior can still depend on:

- display layout
- X11 behavior
- Cinnamon desktop handling
- compositor behavior
- Wine behavior for application wallpapers

---

<a id="troubleshooting"></a>

## 🧯 Troubleshooting

### The wallpaper does not play

Check that:

- `mpv` is installed
- `xwallpaper` is installed
- the file type is supported
- your desktop/session supports the playback method

### Wallpaper Engine item imports but does not work correctly

This usually means the item depends on:

- unsupported scene behavior
- complex HTML behavior
- application-specific runtime behavior
- Wine compatibility issues

### Tray icon is missing

Make sure appindicator support is installed:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

### Application wallpaper stays open after switching

Try switching to another wallpaper again or restarting the app. Application wallpapers are still experimental and runtime behavior may vary.

### Multi-monitor behavior is not what you expect

Check:

- monitor mode
- playlist target
- auto change settings
- whether the wallpaper type supports the selected layout
- your X11 / Cinnamon monitor arrangement

---

<a id="project-status"></a>

## 🚧 Project Status

This project is actively developed and has improved heavily since the first public release.

Current focus areas include:

- stability
- multi-monitor behavior
- better application wallpaper compatibility
- better HTML handling
- cleaner UI and workflow
- improved Wallpaper Engine support where possible

---

<a id="contributing"></a>

## 🤝 Contributing

Bug reports, feedback, ideas, and testing are welcome.

Helpful contributions include:

- reporting bugs
- testing on different Linux Mint setups
- sharing compatibility results
- improving stability
- helping refine Wallpaper Engine support

---

<a id="issues-and-feedback"></a>

## 🐞 Issues and Feedback

If something does not work correctly, please include:

- Linux Mint version
- desktop environment
- whether you use Cinnamon / X11
- package version
- wallpaper type
- steps to reproduce
- screenshots
- terminal output
- whether the issue affects local media, HTML, applications, playlists, or Wallpaper Engine imports

---

<a id="license"></a>

## 📜 License

Add your preferred license here, for example:

- MIT
- GPL-3.0
- Apache-2.0

---

<a id="author"></a>

## 👑 Author

Created by **THXel**
