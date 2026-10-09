# YouTube Music Discord Rich Presence (RPC) for Linux / Chromium

[![Python 3](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Platform Linux](https://img.shields.io/badge/Platform-Linux-orange.svg?logo=linux&logoColor=white)](https://kernel.org)
[![License MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Discord RPC](https://img.shields.io/badge/Discord-Rich%20Presence-5865F2.svg?logo=discord&logoColor=white)](https://discord.com)

A lightweight, standalone Discord Rich Presence daemon for **YouTube Music** running in Chromium, Google Chrome, Brave, or as a PWA on Linux.

---

## ✨ Features

- 📦 **Zero External Dependencies**: Built entirely with Python 3's standard library (`socket`, `struct`, `json`, `subprocess`). No virtualenv, no `pip install`, and no PEP 668 conflicts.
- 🎧 **Native MPRIS Integration**: Automatically detects and reads track information, artist, album, playback status, and position directly from Chromium via `playerctl` / DBus.
- 🖼️ **Automatic HD Album Art**: Fetches high-resolution cover artwork on-the-fly using Deezer and iTunes Search APIs (with in-memory caching), plus a fallback to the official YouTube Music icon.
- ⏱️ **Live Progress Bar**: Displays an accurate playback timeline and elapsed / total duration in Discord when playing.
- ⏸️ **Smart Pause Handling**: Displays `⏸ Paused` state and automatically clears the presence after a configurable timeout (default 5 minutes) so it doesn't linger indefinitely.
- 🔘 **"Listen on YouTube Music" Button**: Allows friends to click your Discord profile and instantly search / open the currently playing track.
- 🔄 **Auto-Reconnect**: Seamlessly reconnects whenever Discord or your browser restarts.
- 🪶 **Ultra Low Resource Usage**: Consumes only ~15 MB of RAM and negligible CPU (~0%).
- 🛠️ **Systemd Integration**: Includes a simple user-level `systemd` service for quiet background execution and auto-start on login.

---

## 📋 Requirements

Ensure the following prerequisites are installed on your Linux system:

1. **Python** (version 3.8 or newer)
2. **playerctl** (CLI media player controller for MPRIS)
3. **Chromium-based browser** (Chromium, Google Chrome, Brave, Edge, Vivaldi) with YouTube Music open (tab or PWA)
4. **Discord** (Official Discord client, Discord Canary, Vesktop, WebCord, ArmCord, etc.)

### Package Installation by Distribution

- **Arch Linux / CachyOS / Manjaro**:
  ```bash
  sudo pacman -S playerctl python
  ```

- **Ubuntu / Debian / Linux Mint**:
  ```bash
  sudo apt update && sudo apt install playerctl python3
  ```

- **Fedora**:
  ```bash
  sudo dnf install playerctl python3
  ```

---

## 🚀 Quick Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/montrevax/youtube-music-discord-rpc.git
   cd youtube-music-discord-rpc
   ```

2. Run the installation script:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

The script will automatically:
- Symlink the executable to `~/.local/bin/ytm-discord-rpc`
- Copy default settings to `~/.config/ytm-discord-rpc/config.json`
- Install and enable the `systemd` user service (`ytm-discord-rpc.service`) to start on login.

---

## 🛠️ Service Management

The daemon runs as a `systemd` user service. You can control it using standard `systemctl --user` commands:

| Task | Command |
|---|---|
| **Check service status** | `systemctl --user status ytm-discord-rpc` |
| **View real-time logs** | `journalctl --user -u ytm-discord-rpc -f` |
| **Restart service** | `systemctl --user restart ytm-discord-rpc` |
| **Stop service** | `systemctl --user stop ytm-discord-rpc` |
| **Start service** | `systemctl --user start ytm-discord-rpc` |
| **Disable auto-start** | `systemctl --user disable ytm-discord-rpc` |

### CLI Commands

You can also interact directly with the CLI:
```bash
ytm-discord-rpc --test    # Test player discovery, artwork lookup, and Discord socket
ytm-discord-rpc --status  # Check daemon status
ytm-discord-rpc --help    # View command-line help
```

---

## ⚙️ Configuration

Configuration is stored in:
`~/.config/ytm-discord-rpc/config.json`

Default options:
```json
{
  "client_id": "1177081335727267940",
  "update_interval": 1.5,
  "show_pause_state": true,
  "pause_timeout_seconds": 300,
  "show_listen_button": true,
  "button_label": "Listen on YouTube Music",
  "fallback_icon": "https://music.youtube.com/img/favicon_144.png",
  "play_icon": "https://raw.githubusercontent.com/material-icons/material-icons/master/png/av/play_arrow/baseline_play_arrow_white_48dp.png",
  "pause_icon": "https://raw.githubusercontent.com/material-icons/material-icons/master/png/av/pause/baseline_pause_white_48dp.png"
}
```

### Parameter Description:

- `client_id`: Discord Application ID (you can provide your own from the Discord Developer Portal).
- `update_interval`: Polling interval in seconds (default `1.5`).
- `show_pause_state`: Whether to show presence while paused (`true` / `false`).
- `pause_timeout_seconds`: Seconds before clearing presence when music remains paused (`300` = 5 minutes).
- `show_listen_button`: Whether to display a button linking to the track (`true` / `false`).
- `button_label`: Label displayed on the action button.

*After making changes, restart the service to apply:*
```bash
systemctl --user restart ytm-discord-rpc
```

---

## 🔍 Troubleshooting

1. **Activity not showing up on your Discord profile:**
   - Open Discord: **User Settings -> Activity Privacy**.
   - Make sure **"Display current activity as a status message"** is toggled **ON**.

2. **Player not detected:**
   - Verify that Chromium exposes MPRIS controls:
     ```bash
     playerctl -l
     ```
     You should see `chromium.instance...` listed when media is playing or paused.
   - If not visible, ensure Hardware Media Key Handling is active in your browser: navigate to `chrome://flags/#hardware-media-key-handling` and set it to `Default` or `Enabled`.

3. **Run Diagnostic Test:**
   - Run the built-in diagnostic test:
     ```bash
     ytm-discord-rpc --test
     ```
   - This checks player detection, track metadata reading, album art resolution, and IPC socket connection to Discord step-by-step.

---

## 🗑️ Uninstallation

To cleanly remove the service, configuration, and binary link:
```bash
./uninstall.sh
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
