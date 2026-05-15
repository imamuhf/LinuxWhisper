"""
Recording overlay visibility management.
"""
from __future__ import annotations

from linuxwhisper.decorators import run_on_main_thread
from linuxwhisper.state import STATE

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib


class OverlayManager:
    """Manages recording overlay visibility."""

    @staticmethod
    @run_on_main_thread
    def show(mode: str) -> None:
        """Show overlay for given mode."""
        OverlayManager._show_impl(mode)

    @staticmethod
    def _show_impl(mode: str) -> None:
        from linuxwhisper.ui.recording_overlay import GtkOverlay
        if STATE.overlay_window:
            try:
                STATE.overlay_window.close()
            except Exception:
                pass
        STATE.overlay_window = GtkOverlay(mode)

    @staticmethod
    @run_on_main_thread
    def show_text(text: str, is_response: bool = False) -> None:
        """Update overlay with transcribed text preview."""
        if STATE.overlay_window:
            STATE.overlay_window.set_text(text, is_response=is_response)
        else:
            OverlayManager._show_impl("dictation")
            STATE.overlay_window.set_text(text, is_response=is_response)

    @staticmethod
    @run_on_main_thread
    def hide() -> None:
        """Hide overlay."""
        OverlayManager._hide_impl()

    @staticmethod
    def _hide_impl() -> None:
        if STATE.overlay_window:
            try:
                STATE.overlay_window.close()
            except Exception:
                pass
            STATE.overlay_window = None
