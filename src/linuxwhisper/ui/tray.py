"""
System tray (AppIndicator) management via subprocess.

The tray icon lives in a subprocess (tray_process.py) because
AyatanaAppIndicator3 depends on Gtk 3.0 internally and needs its
own Gtk main loop.

Communication: Unix socket pair, newline-delimited JSON.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from typing import Any, Dict

import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from linuxwhisper.state import STATE


class TrayManager:
    """System tray (AppIndicator) management via subprocess."""

    _proc: subprocess.Popen | None = None
    _sock: socket.socket | None = None
    _available: bool | None = None

    @classmethod
    def start(cls) -> None:
        """Launch the tray subprocess and enter the main loop."""
        if not cls._check_available():
            print(
                "\u26a0\ufe0f AyatanaAppIndicator3 not available \u2014 running without tray icon."
            )
            print(
                "   Install: libayatana-appindicator (Arch) or gir1.2-ayatanaappindicator3-0.1 (Debian)"
            )
            Gtk.init([])
            Gtk.main()
            return

        cls._spawn()

        chan = GLib.IOChannel.unix_new(cls._sock.fileno())
        chan.add_watch(GLib.IO_IN | GLib.IO_HUP, cls._on_event)

        Gtk.init([])
        Gtk.main()

    @classmethod
    def update_menu(cls) -> None:
        """Send current state to the tray process so it rebuilds the menu."""
        if not cls._sock:
            return
        state = {
            "chat_enabled": STATE.chat_enabled,
            "toggle_mode": STATE.toggle_mode,
            "whisper_model": STATE.whisper_model,
            "answer_history": STATE.answer_history[:5],
        }
        cls._send({"cmd": "update_menu", "state": state})

    @classmethod
    def _check_available(cls) -> bool:
        if cls._available is not None:
            return cls._available
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import gi; gi.require_version('AyatanaAppIndicator3', '0.1'); "
                    "from gi.repository import AyatanaAppIndicator3; print('ok')",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            cls._available = result.returncode == 0 and "ok" in result.stdout
        except Exception:
            cls._available = False
        return cls._available

    @classmethod
    def _spawn(cls) -> None:
        parent_sock, child_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        parent_sock.setblocking(False)
        cls._sock = parent_sock

        tray_module = os.path.join(os.path.dirname(__file__), "tray_process.py")
        cls._proc = subprocess.Popen(
            [sys.executable, tray_module, str(child_sock.fileno())],
            pass_fds=(child_sock.fileno(),),
            close_fds=True,
        )
        child_sock.close()

    @classmethod
    def _send(cls, msg: Dict[str, Any]) -> None:
        if cls._sock:
            try:
                cls._sock.sendall((json.dumps(msg) + "\n").encode())
            except OSError:
                pass

    @classmethod
    def _on_event(cls, source, condition) -> bool:
        if condition == GLib.IO_HUP:
            cls._cleanup()
            return False
        try:
            data = cls._sock.recv(65536)
            if not data:
                cls._cleanup()
                return False
            for line in data.decode().strip().split("\n"):
                line = line.strip()
                if line:
                    cls._handle_event(json.loads(line))
        except (BlockingIOError, json.JSONDecodeError):
            pass
        return True

    @classmethod
    def _handle_event(cls, event: Dict[str, Any]) -> None:
        ev = event.get("event")
        if ev == "chat_toggle":
            STATE.chat_enabled = event["active"]
            from linuxwhisper.state import SettingsManager

            SettingsManager.save(STATE)
            from linuxwhisper.managers.chat import ChatManager

            if not STATE.chat_enabled:
                ChatManager._destroy()
            else:
                ChatManager.refresh_overlay()
        elif ev == "mode_toggle":
            STATE.toggle_mode = event["active"]
            from linuxwhisper.state import SettingsManager

            SettingsManager.save(STATE)
        elif ev == "model_switch":
            STATE.whisper_model = event["model"]
            print(f"\U0001f399\ufe0f Dictation model switched to: {event['model']}")
            from linuxwhisper.state import SettingsManager

            SettingsManager.save(STATE)
        elif ev == "show_settings":
            from linuxwhisper.ui.settings_dialog import SettingsDialog

            SettingsDialog.show()
        elif ev == "clear_history":
            from linuxwhisper.managers.history import HistoryManager

            HistoryManager.clear_all()
        elif ev == "history_click":
            idx = event["index"]
            if idx < len(STATE.answer_history):
                import re

                from linuxwhisper.services.clipboard import ClipboardService

                clean = re.sub(r"^\[.*?\]\s*", "", STATE.answer_history[idx]["text"])
                ClipboardService.paste_text(clean)
        elif ev == "quit":
            cls._cleanup()
            Gtk.main_quit()
            os._exit(0)

    @classmethod
    def _cleanup(cls) -> None:
        if cls._proc:
            try:
                cls._proc.terminate()
                cls._proc.wait(timeout=3)
            except Exception:
                cls._proc.kill()
            cls._proc = None
        if cls._sock:
            try:
                cls._sock.close()
            except OSError:
                pass
            cls._sock = None
