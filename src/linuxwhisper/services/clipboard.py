"""
Clipboard operations for typing and pasting text.

Uses the platform abstraction layer to work on both X11 and Wayland.
Detects terminal emulators and uses the correct keyboard shortcuts
(Ctrl+Shift+V/C instead of Ctrl+V/C).
"""
from __future__ import annotations

import time

from linuxwhisper.platform import get_clipboard, get_input


class ClipboardService:
    """Clipboard operations for typing and pasting text."""

    @staticmethod
    def type_text(text: str, is_terminal: bool = False) -> None:
        """Type text at cursor via clipboard-paste bridge."""
        if not text:
            return

        inp = get_input()
        clipboard = get_clipboard()

        try:
            original = clipboard.paste()
        except Exception:
            original = None

        clean_text = f" {text.strip()}" if not text.startswith(" ") else text
        inp.type_text(clean_text, is_terminal=is_terminal)

        time.sleep(0.1)
        if original is not None:
            try:
                clipboard.copy(original)
            except Exception:
                pass

    @staticmethod
    def copy_selected() -> str:
        """Copy currently selected text and return it."""
        clipboard = get_clipboard()
        inp = get_input()
        is_term = inp.is_terminal_focused()
        inp.simulate_copy(is_terminal=is_term)
        time.sleep(0.1)
        return clipboard.paste().strip()

    @staticmethod
    def paste_text(text: str) -> None:
        """Paste text directly via clipboard."""
        clipboard = get_clipboard()
        inp = get_input()
        clipboard.copy(text)
        time.sleep(0.15)  # let wl-clip-persist re-offer data
        is_term = inp.is_terminal_focused()
        inp.simulate_paste(is_terminal=is_term)
