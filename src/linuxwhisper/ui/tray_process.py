"""
Standalone GTK3(+Ayatana) tray process — spawned by tray.py.

Communication with the parent process via a Unix socket pair.
Protocol: newline-delimited JSON messages.

Parent → child commands:
  {"cmd": "update_menu", "chat_enabled": bool, "toggle_mode": bool,
   "whisper_model": str, "answer_history": [...]}

Child → parent events:
  {"event": "chat_toggle", "active": bool}
  {"event": "mode_toggle", "active": bool}
  {"event": "model_switch", "model": str}
  {"event": "show_settings"}
  {"event": "clear_history"}
  {"event": "history_click", "index": int}
  {"event": "quit"}
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
from typing import Any, Dict

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AyatanaAppIndicator3 as AppIndicator


class TrayProcess:
    """Owns the AppIndicator and its GTK3 menu. Talks to parent over a socket."""

    def __init__(self, sock_fd: int):
        self.sock = socket.fromfd(sock_fd, socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.setblocking(False)
        self.indicator: Any = None

        GLib.io_add_watch(self.sock, GLib.IO_IN | GLib.IO_HUP, self._on_message)

        self._build_indicator()
        self._update_menu({})

    # ── Indicator setup ──────────────────────────────────────────────

    def _build_indicator(self) -> None:
        self.indicator = AppIndicator.Indicator.new(
            "linuxwhisper",
            "emblem-favorite",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("LinuxWhisper")

    # ── Menu building ────────────────────────────────────────────────

    def _build_menu(self, state: Dict[str, Any]) -> Gtk.Menu:
        menu = Gtk.Menu()

        history = state.get("answer_history", [])
        if history:
            for i, item in enumerate(history[:5]):
                preview = item["text"][:50].replace("\n", " ")
                if len(item["text"]) > 50:
                    preview += "..."
                label = f"[{item['timestamp']}] {preview}"
                mi = Gtk.MenuItem(label=label)
                mi.connect("activate", lambda w, idx=i: self._send({"event": "history_click", "index": idx}))
                menu.append(mi)
            menu.append(Gtk.SeparatorMenuItem())
        else:
            empty = Gtk.MenuItem(label="(No History)")
            empty.set_sensitive(False)
            menu.append(empty)
            menu.append(Gtk.SeparatorMenuItem())

        clear = Gtk.MenuItem(label="Clear History")
        clear.connect("activate", lambda w: self._send({"event": "clear_history"}))
        menu.append(clear)
        menu.append(Gtk.SeparatorMenuItem())

        chat_toggle = Gtk.CheckMenuItem(label="Show Chat Overlay")
        chat_toggle.set_active(state.get("chat_enabled", True))
        chat_toggle.connect("toggled", lambda w: self._send({"event": "chat_toggle", "active": w.get_active()}))
        menu.append(chat_toggle)

        toggle_mode = Gtk.CheckMenuItem(label="Toggle Mode (Press to Record)")
        toggle_mode.set_active(state.get("toggle_mode", False))
        toggle_mode.connect("toggled", lambda w: self._send({"event": "mode_toggle", "active": w.get_active()}))
        menu.append(toggle_mode)

        model_menu = Gtk.Menu()
        model_group = None
        for model in ("base", "small", "medium", "large-v3"):
            item = Gtk.RadioMenuItem(group=model_group, label=model)
            if model_group is None:
                model_group = item
            if model == state.get("whisper_model", "base"):
                item.set_active(True)
            item.connect("toggled", lambda w, m=model: self._send({"event": "model_switch", "model": m}) if w.get_active() else None)
            model_menu.append(item)

        model_item = Gtk.MenuItem(label="Dictation Model")
        model_item.set_submenu(model_menu)
        menu.append(model_item)

        settings_item = Gtk.MenuItem(label="Settings")
        settings_item.connect("activate", lambda w: self._send({"event": "show_settings"}))
        menu.append(settings_item)
        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda w: self._send({"event": "quit"}))
        menu.append(quit_item)

        menu.show_all()
        return menu

    # ── Command handling ─────────────────────────────────────────────

    def _update_menu(self, state: Dict[str, Any]) -> None:
        menu = self._build_menu(state)
        self.indicator.set_menu(menu)

    def _on_message(self, source, condition) -> bool:
        if condition == GLib.IO_HUP:
            Gtk.main_quit()
            return False
        try:
            data = self.sock.recv(65536)
            if not data:
                Gtk.main_quit()
                return False
            for line in data.decode().strip().split("\n"):
                line = line.strip()
                if line:
                    msg = json.loads(line)
                    self._handle_cmd(msg)
        except (BlockingIOError, json.JSONDecodeError):
            pass
        return True

    def _handle_cmd(self, msg: Dict[str, Any]) -> None:
        cmd = msg.get("cmd")
        if cmd == "update_menu":
            self._update_menu(msg.get("state", {}))
        elif cmd == "quit":
            Gtk.main_quit()

    # ── Sending events back to parent ────────────────────────────────

    def _send(self, event: Dict[str, Any]) -> None:
        try:
            self.sock.sendall((json.dumps(event) + "\n").encode())
        except OSError:
            pass

    # ── Entry point ──────────────────────────────────────────────────

    def run(self) -> None:
        Gtk.main()


def main() -> None:
    sock_fd = int(sys.argv[1])
    proc = TrayProcess(sock_fd)
    proc.run()


if __name__ == "__main__":
    main()
