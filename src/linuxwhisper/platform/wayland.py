"""
Wayland platform backends.

Uses: ydotool, wl-copy, wl-paste, grim
Compositor-specific: niri msg (optional, for terminal detection)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from typing import Tuple

from linuxwhisper.platform.base import ClipboardBackend, InputBackend, ScreenshotBackend

logger = logging.getLogger(__name__)

# Terminal app-ids matched against focused window info (lowercase).
_TERMINAL_KEYWORDS: Tuple[str, ...] = (
    "terminal", "terminator", "tilix", "alacritty", "kitty",
    "konsole", "xterm", "urxvt", "sakura", "terminology",
    "guake", "tilda", "yakuake", "wezterm", "foot",
    "cool-retro-term", "hyper", "tabby", "rio", "ghostty",
)


class WaylandClipboard(ClipboardBackend):
    """Clipboard via wl-copy / wl-paste (Wayland)."""

    def copy(self, text: str) -> None:
        try:
            proc = subprocess.Popen(
                ["wl-copy"],
                stdin=subprocess.PIPE,
            )
            proc.communicate(input=text.encode("utf-8"))
        except Exception as e:
            print(f"⚠️ Wayland clipboard copy error: {e}")

    def paste(self) -> str:
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout
        except Exception:
            return ""


class WaylandInput(InputBackend):
    """Input simulation via ydotool raw scancodes (Wayland).

    Uses a clipboard-paste bridge: wl-copy → ydotool key (raw scancodes).
    Raw scancodes bypass Wayland protocol restrictions (zwp_virtual_keyboard_v1)
    that block named keys like ``ctrl+v`` on KDE Plasma 6.

    ydotool requires its daemon (ydotoold) running. We attempt to
    auto-start it on init if not already running.
    """

    # Raw scancodes (kernel keycodes, layout-agnostic):
    #   29 = Left Ctrl, 42 = Left Shift, 46 = C, 47 = V
    _CTRL_V = ["29:1", "47:1", "47:0", "29:0"]
    _CTRL_C = ["29:1", "46:1", "46:0", "29:0"]
    _CTRL_SHIFT_V = ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]
    _CTRL_SHIFT_C = ["29:1", "42:1", "46:1", "46:0", "42:0", "29:0"]

    def __init__(self) -> None:
        self._ensure_daemon()

    @staticmethod
    def _ensure_daemon() -> None:
        try:
            r = subprocess.run(
                ["pgrep", "-x", "ydotoold"],
                capture_output=True, timeout=2,
            )
            if r.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        logger.info("ydotoold not running — attempting to start it...")
        socket_path = f"/run/user/{os.getuid()}/.ydotool_socket"
        try:
            subprocess.Popen(
                ["ydotoold"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for socket to be ready (up to 2s)
            for _ in range(20):
                if os.path.exists(socket_path):
                    break
                time.sleep(0.1)
        except FileNotFoundError:
            logger.error("ydotoold not found. Install ydotool, then start ydotoold manually.")
        except Exception as e:
            logger.error("Failed to start ydotoold: %s", e)

    def _run(self, args: list[str]) -> None:
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=2)
            if r.returncode != 0:
                logger.debug("ydotool error (rc=%d): %s", r.returncode, r.stderr.strip())
        except FileNotFoundError:
            logger.error("ydotool not found — install ydotool and start ydotoold")
        except subprocess.TimeoutExpired:
            logger.debug("ydotool timed out")
        except Exception as e:
            logger.debug("ydotool exception: %s", e)

    def _key(self, scancodes: list[str]) -> None:
        """Send raw scancodes via ydotool."""
        self._run(["ydotool", "key", *scancodes])

    def type_text(self, text: str, is_terminal: bool = False) -> None:
        """Bridge: wl-copy text, then Ctrl+V (/Shift) via raw scancodes."""
        try:
            proc = subprocess.Popen(
                ["wl-copy"],
                stdin=subprocess.PIPE,
            )
            proc.communicate(input=text.encode("utf-8"))
        except Exception as e:
            logger.debug("wl-copy error in type_text: %s", e)
            return
        self._key(self._CTRL_SHIFT_V if is_terminal else self._CTRL_V)

    def simulate_paste(self, is_terminal: bool = False) -> None:
        if is_terminal:
            self._key(self._CTRL_SHIFT_V)
        else:
            self._key(self._CTRL_V)

    def simulate_copy(self, is_terminal: bool = False) -> None:
        if is_terminal:
            self._key(self._CTRL_SHIFT_C)
        else:
            self._key(self._CTRL_C)

    def is_terminal_focused(self) -> bool:
        """
        Detect focused terminal via compositor IPC.

        Currently supports niri (via `niri msg focused-window`).
        Returns False for unsupported compositors (safe default → Ctrl+V).
        """
        try:
            result = subprocess.run(
                ["niri", "msg", "-j", "focused-window"],
                capture_output=True, text=True, timeout=1,
            )
            if result.returncode == 0 and result.stdout.strip():
                info = json.loads(result.stdout)
                app_id = (info.get("app_id") or "").lower()
                title = (info.get("title") or "").lower()
                combined = f"{app_id} {title}"
                return any(kw in combined for kw in _TERMINAL_KEYWORDS)
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            pass

        return False


class WaylandScreenshot(ScreenshotBackend):
    """Screenshot using spectacle (KDE Plasma 6 Wayland)."""

    def take_screenshot(self, output_path: str) -> bool:
        uid = os.getuid()

        # Kill zombie spectacle instances to prevent D-Bus deadlocks
        subprocess.run(
            ["killall", "-q", "spectacle"],
            stderr=subprocess.DEVNULL,
        )

        # Inject full KDE/Wayland/D-Bus env so spectacle finds the portal
        env = os.environ.copy()
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{uid}/bus")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
        env.setdefault("WAYLAND_DISPLAY", "wayland-0")
        env.setdefault("XDG_CURRENT_DESKTOP", "KDE")
        env.setdefault("XDG_SESSION_TYPE", "wayland")

        try:
            subprocess.run(
                ["spectacle", "-b", "-n", "-o", output_path],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=True,
            )
            time.sleep(0.05)
            return True
        except subprocess.TimeoutExpired:
            print("⚠️ spectacle D-Bus timeout — portal blocked")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ spectacle failed (rc={e.returncode})")
        except FileNotFoundError:
            print("⚠️ spectacle not found")
        except Exception as e:
            print(f"⚠️ spectacle error: {e}")
        return False
