<div align="center">

<img src="assets/logo.png" alt="LinuxWhisper Logo" width="180" height="auto" />

# LinuxWhisper

**A Voice-Assistant & AI Companion for Linux**

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](LICENSE)
[![Groq Powered](https://img.shields.io/badge/AI-Groq%20Cloud-orange?style=for-the-badge)](https://groq.com)

---

**LinuxWhisper** is a simple voice assistant designed to help you with daily tasks. It uses global hotkeys to provide AI-powered tools without switching windows.

<br />

![LinuxWhisper Demo](assets/demo.gif)

</div>

## Features

- 🎙️ **Dictation**: Voice-to-text at your cursor using **Whisper-v3**.
- 💬 **AI Chat**: Helpful Q&A and conversation.
- ✍️ **Smart Rewrite**: Modify selected text using your voice.
- 👁️ **Vision**: Understand screenshots using **Llama 4**.
- 🔊 **Voice Feedback**: Optional text-to-speech for AI responses.

---

## 🖥️ Supported Platforms

| Distribution | Display Server | Status |
|:---|:---|:---|
| **Debian / Ubuntu** | X11 | ✅ Fully supported |
| **Debian / Ubuntu** | Wayland | ✅ Supported |
| **Arch Linux** | X11 | ✅ Supported |
| **Arch Linux** | Wayland / **Niri** | ✅ Fully supported |

The app auto-detects your session type (X11 or Wayland) and uses the appropriate backends:

| Feature | X11 | Wayland |
|:---|:---|:---|
| Clipboard | `xclip` | `wl-clipboard` |
| Key Simulation | `xdotool` | `ydotool` |
| Screenshots | `gnome-screenshot` | `grim` |
| Overlays | GTK Window Hints | `gtk-layer-shell` |
| Global Hotkeys | `evdev` | `evdev` |

---

## ⌨️ Command Center

| Key | Action | Purpose |
|:---:|:---|:---|
| `R-Alt` / `F3` | **Dictate** | Transcribe voice to text at cursor |
| `R-Ctrl` | **Term Dictate** | Dictate into terminal (Ctrl+Shift+V) |
| `F4` | **Chat** | Open/Focus AI conversation |
| `F7` | **Rewrite** | Highlight text → Speak to modify |
| `F8` | **Vision** | Screenshot + Intelligent Analysis |
| `F9` | **Pin** | Toggle "Always on Top" for chat |
| `F10` | **TTS** | Toggle AI voice feedback |

---

## 🛠️ Quick Start

### 1. Requirements
*   **Linux** (Debian/Ubuntu or Arch Linux)
*   **Groq API Key**: [Get your free key here](https://console.groq.com)
*   **User in `input` group** (for global hotkeys):
    ```bash
    sudo usermod -aG input $USER
    # Log out and back in after this
    ```

### 2. Installation
```bash
git clone https://github.com/imamuhf/LinuxWhisper.git && cd LinuxWhisper
./setup.sh
```

The setup script automatically detects your distribution and session type, then installs the correct packages.

### 3. Launch
```bash
# Set your API Key once
export GROQ_API_KEY="your_key"

# Start the whisperer
linuxwhisper

# Or alternatively:
python -m linuxwhisper
```

> [!TIP]
> Use the **System Tray** icon or the ⚙️ icon in the chat overlay to adjust TTS voices and preferences.

---

## 🔧 Wayland Clipboard-Paste Bridge (KDE Plasma 6 Workaround)

On **KDE Plasma 6 (Wayland)**, the `zwp_virtual_keyboard_v1` protocol is restricted, blocking tools like `wtype`. This fork implements a **clipboard-paste bridge** using raw kernel scancodes as a workaround.

### How it works

Rather than injecting keystrokes via Wayland protocols (blocked), the program:

1. **Stores transcribed text** to the Wayland clipboard via `wl-copy`
2. **Sends raw scancodes** via `ydotool` — writing directly to `/dev/uinput` at the kernel level, completely bypassing Wayland

This approach is:
- **Layout-agnostic** — raw scancodes for `Ctrl+V` work regardless of keyboard layout
- **Unicode-safe** — clipboard handles Korean, Japanese, Arabic, Hebrew, etc.
- **Fast** — pastes entire paragraphs instantly vs. character-by-character injection

### Requirements

```bash
# ydotool daemon (auto-started by LinuxWhisper on first use)
sudo pacman -S ydotool

# uinput permissions (one-time setup)
echo 'KERNEL=="uinput", GROUP="input", MODE="0660"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# You must be in the 'input' group
sudo usermod -aG input $USER
```

### Key simulation reference

| Action | Raw scancodes |
|--------|--------------|
| `Ctrl+V` | `ydotool key 29:1 47:1 47:0 29:0` |
| `Ctrl+C` | `ydotool key 29:1 46:1 46:0 29:0` |
| `Ctrl+Shift+V` | `ydotool key 29:1 42:1 47:1 47:0 42:0 29:0` |
| `Ctrl+Shift+C` | `ydotool key 29:1 42:1 46:1 46:0 42:0 29:0` |

`29` = Left Ctrl, `42` = Left Shift, `46` = C, `47` = V | `:1` = press, `:0` = release

---

### Niri Users

For best overlay behaviour, add these rules to `~/.config/niri/config.kdl`:

```kdl
layer-rule {
    match namespace="linuxwhisper-recording"
    shadow { on false }
}

layer-rule {
    match namespace="linuxwhisper-chat"
    shadow { on false }
}
```

---

## 📂 Project Structure

```
src/linuxwhisper/
├── __init__.py          # Package version
├── __main__.py          # python -m linuxwhisper
├── app.py               # main() entry point
├── config.py            # Config dataclass + CFG singleton
├── state.py             # AppState + SettingsManager + STATE
├── api.py               # Groq client initialization
├── decorators.py        # safe_execute, run_on_main_thread
├── platform/
│   ├── __init__.py      # Session detection + backend factory
│   ├── base.py          # Abstract base classes (ABCs)
│   ├── x11.py           # X11 backends (xdotool, xclip, gnome-screenshot)
│   └── wayland.py       # Wayland backends (ydotool, wl-clipboard, grim)
├── services/
│   ├── audio.py         # AudioService (recording + transcription)
│   ├── ai.py            # AIService (chat + vision)
│   ├── tts.py           # TTSService (Orpheus voice)
│   ├── clipboard.py     # ClipboardService (uses platform backends)
│   └── image.py         # ImageService (uses platform backends)
├── managers/
│   ├── history.py       # HistoryManager (conversation + tray history)
│   ├── chat.py          # ChatManager (overlay state + auto-hide)
│   └── overlay.py       # OverlayManager (recording indicator)
├── ui/
│   ├── recording_overlay.py  # GtkOverlay (waveform + gtk-layer-shell)
│   ├── chat_overlay.py       # ChatOverlay (WebKit2 + gtk-layer-shell)
│   ├── settings_dialog.py    # SettingsDialog (voice, schemes, hotkeys)
│   └── tray.py               # TrayManager (AppIndicator)
└── handlers/
    ├── mode.py           # ModeHandler (dictation/AI/rewrite/vision)
    └── keyboard.py       # KeyboardHandler (evdev listener)
```
