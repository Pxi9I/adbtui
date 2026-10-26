# adbtui

A lightweight **terminal UI (TUI)** for ADB and Fastboot — menu-driven interface that wraps the Android SDK Platform Tools without losing CLI transparency.

Every action shows the exact command it runs, so it's still a command-line tool, just with an easy-to-navigate menu on top.

**Python 3.6+, standard library only. Multiplatform (Linux, macOS, Windows).**

---

## Features

### ADB
- List devices with details (`adb devices -l`)
- Device info: model, manufacturer, Android version, build, security patch, bootloader, slot, battery status
- Interactive shell (`adb shell`)
- Live logcat with color (`adb logcat`)
- Install APK with `-r` (replace)
- Uninstall app (optionally keep data with `-k`)
- List packages (filter, user apps only)
- Push/pull files
- Take screenshot to PNG
- Sideload ZIP
- Wireless pairing (`adb pair`) and connection (`adb connect`)
- Reboot: system, bootloader, recovery, fastbootd
- Custom adb commands

### Fastboot
- List devices
- Dump all variables (`getvar all`)
- Flash image to partition
- Boot image without flashing
- Erase partition
- Set active slot (a/b)
- Unlock/lock bootloader
- Wipe user data (`-w`)
- Reboot: system, bootloader, fastbootd, recovery
- Custom fastboot commands

### General
- Select device when multiple are connected (adds `-s <serial>`)
- Restart ADB server
- Auto-refresh device list
- Path completion in input fields (Tab key)
- Pager for output with scroll navigation

---

## Installation

### Linux (Arch/CachyOS)
```bash
sudo pacman -S android-tools
```

### Linux (Debian/Ubuntu)
```bash
sudo apt install adb fastboot
```

### Linux (Fedora/RHEL)
```bash
sudo dnf install android-tools
```

### macOS
```bash
brew install android-platform-tools
```

### Windows
1. Download [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools)
2. Extract and add to PATH
3. Or use `pip install android-tools` (if available in your environment)

### Install adbtui
```bash
chmod +x adbtui_en.py
./adbtui_en.py
```

---

## Usage

### Start
```bash
./adbtui_en.py
```

### Help
```bash
./adbtui_en.py --help
./adbtui_en.py -h
./adbtui_en.py -help
```

### Controls
| Key | Action |
|-----|--------|
| **↑ / k** | Move up |
| **↓ / j** | Move down |
| **Enter** | Select/run |
| **1–9** | Jump to item |
| **r** | Refresh device list |
| **q / Esc** | Back / quit |
| **Space / PgDn** | Page down (in pager) |
| **PgUp** | Page up (in pager) |
| **g** | Go to top (in pager) |
| **G** | Go to bottom (in pager) |

---

## Screenshots

Top menu shows:
- Connected ADB devices (status: device, offline, etc.)
- Connected Fastboot devices
- Currently selected device (or "auto" for default)

Each submenu (ADB, Fastboot) displays available operations. Select and press Enter. Dangerous operations (flash, erase, unlock, wipe) require confirmation.

---

## Why TUI?

- **Transparent**: Every command shown before execution, so you learn what's happening under the hood
- **Convenience**: Navigate with arrow keys instead of remembering dozens of adb/fastboot flags
- **Multiplatform**: Pure Python + curses, runs on Linux, macOS, Windows
- **Minimal**: Standard library only — no pip dependencies
- **Safe**: Confirmation prompts for destructive operations

---

## Requirements

- Python 3.6+
- `adb` and `fastboot` tools in PATH
- Terminal with curses support (all modern terminals)

**No external Python dependencies.**

---

## License

MIT License. See LICENSE file for details.

---

## Troubleshooting

### `adb: command not found`
Install Android SDK Platform Tools (see Installation section).

### Menu doesn't display correctly
Ensure your terminal window is at least 60 characters wide and 15 lines tall. Update the `TERM` environment variable if colors are broken:
```bash
export TERM=xterm-256color
./adbtui_en.py
```

### Can't see devices
- Check device is connected: `adb devices`
- Enable USB debugging in device settings
- Try `./adbtui_en.py` → Restart ADB server
- On Linux, you may need udev rules:
  ```bash
  sudo curl https://raw.githubusercontent.com/M0Rf30/android-udev-rules/main/51-android.rules \
    -o /etc/udev/rules.d/51-android.rules
  sudo udevadm control --reload
  ```

### Wireless connection won't pair
- Device and computer must be on the same network
- Device must show the pairing prompt with code and port
- Enter the port shown on the pairing screen

---

## Contributing

Issues, feature requests, and pull requests are welcome.

---

## Author

Created as a practical CLI wrapper with a menu — because sometimes point-and-click beats memorizing flags.
