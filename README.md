![Linux Mint Wallpaper Studio Banner](https://raw.githubusercontent.com/THXel/Linux-Mint-Wallpaper-Studio-/main/Mint%20Wallpaper%20Studio%20Logo.png)

# Linux Mint Wallpaper Studio

**Linux Mint Wallpaper Studio** is a wallpaper manager for **Linux Mint** with support for local wallpapers, video wallpapers, playlists, preview tools, and Wallpaper Engine workshop sync.

It is designed to make animated desktop wallpapers easier to manage on Linux Mint with a clean UI and simple workflow.

---

## Features

* Support for **local image wallpapers**
* Support for **local video wallpapers**
* **Wallpaper Engine sync** for workshop items containing directly usable image or video files
* **Playlist management**
* **Random wallpaper switching** with timer support
* **Preview panel** with file details
* **Thumbnail previews** for videos
* **Click-to-preview popup player**
* **Multi-monitor playlist target selection**
* **Sync mode support** for monitor behavior
* **Audio controls** for video wallpapers, including mute and volume slider
* **Add Media window** with file and folder import
* **Drag & drop support** when `tkinterdnd2` is available
* **Scene Inspector** for unsupported Wallpaper Engine items

---

## Supported Wallpaper Types

### Supported

* Local image wallpapers
* Local video wallpapers
* Wallpaper Engine workshop items that contain directly usable **image** or **video** files

### Not supported as live wallpapers

* Wallpaper Engine **Scene** wallpapers
* Wallpaper Engine **Application** wallpapers
* Wallpaper Engine **Web / HTML** wallpapers

These unsupported types can still be detected and inspected, but they are not currently played as native live wallpapers.

---

## Installation

### Option 1: Install the `.deb` package

Download the latest release package and install it with:

```bash
cd ~/Downloads
sudo dpkg -i mint-wallpaper-studio_0.1.37_all_htmldebugwindow.deb
sudo apt -f install
```

Then launch it with:

```bash
mint-wallpaper-studio
```

---

## Dependencies

The current package uses these system dependencies:

* `python3`
* `python3-tk`
* `python3-pil`
* `python3-pystray`
* `python3-gi`
* `mpv`
* `x11-utils`
* `wmctrl`
* `gir1.2-ayatanaappindicator3-0.1`
* `libnotify-bin`
* `gir1.2-webkit2-4.1`

If needed, you can install them manually with:

```bash
sudo apt install python3 python3-tk python3-pil python3-pystray python3-gi mpv x11-utils wmctrl gir1.2-ayatanaappindicator3-0.1 libnotify-bin gir1.2-webkit2-4.1
```

---

## Usage

After installation, start the app from:

* the application menu, or
* the terminal with:

```bash
mint-wallpaper-studio
```

Typical workflow:

1. Add media from files or folders
2. Preview wallpapers before applying them
3. Organize entries in playlists
4. Choose monitor targets for playback
5. Use random switching or playlist controls for automatic wallpaper changes

---

## Wallpaper Engine Support

Linux Mint Wallpaper Studio can work with Wallpaper Engine workshop content **when the item contains directly usable media files**, such as videos or images.

### Important note

Not every Wallpaper Engine item can be used as a Linux live wallpaper.

Items based on:

* Scene rendering
* Web technologies / HTML
* Application-based runtime content

are currently not supported as full live wallpapers in the same way they work on Windows Wallpaper Engine.

---

## Notes

* Video wallpaper playback depends on `mpv`.
* Some features are intended for **Linux Mint / Cinnamon on X11**.
* Drag & drop support depends on bundled or available `tkinterdnd2` support.
* Unsupported Wallpaper Engine item types can still appear in sync results for inspection.
* Behavior may vary depending on desktop environment, compositor, and multi-monitor setup.

---

## Project Status

This project is actively being developed and improved.

Current focus areas include:

* UI improvements
* better playlist handling
* improved preview workflow
* better multi-instance handling
* extended Wallpaper Engine compatibility where possible

---

## Known Limitations

* Scene wallpapers are not supported as native live wallpapers
* Application wallpapers are not supported
* Web / HTML wallpapers are not fully supported as live wallpapers
* Linux desktop environments may behave differently depending on X11 setup and wallpaper embedding behavior

---

## Contributing

Contributions, ideas, bug reports, and feedback are welcome.

You can help by:

* reporting bugs
* suggesting UI improvements
* testing on different Linux Mint setups
* improving compatibility and stability

---

## Issues and Feedback

If something does not work correctly, please open an issue and include:

* Linux Mint version
* desktop environment
* installation method
* steps to reproduce the issue
* screenshots or terminal output if available

---

## License

Add your preferred license here.

For example:

* MIT
* GPL-3.0
* Apache-2.0

---

## Author

Created by **THXel**.
