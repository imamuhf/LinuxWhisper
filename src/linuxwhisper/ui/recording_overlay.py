"""
Floating recording overlay with transcription preview.

On Wayland: uses gtk-layer-shell for proper overlay behaviour.
On X11: uses classic GTK window hints (POPUP, keep-above).
"""
from __future__ import annotations

from linuxwhisper.config import CFG
from linuxwhisper.platform import SESSION_TYPE
from linuxwhisper.state import STATE

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GLib, Gtk

# Optional gtk-layer-shell for Wayland
try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
    HAS_LAYER_SHELL = True
except (ValueError, ImportError):
    HAS_LAYER_SHELL = False


class GtkOverlay(Gtk.Window):
    """Floating recording overlay with waveform visualization."""

    def __init__(self, mode: str):
        # Layer-shell requires TOPLEVEL; X11 uses POPUP
        if HAS_LAYER_SHELL and SESSION_TYPE == "wayland":
            super().__init__(type=Gtk.WindowType.TOPLEVEL)
        else:
            super().__init__(type=Gtk.WindowType.POPUP)

        self.mode = mode
        self.config = CFG.MODES.get(mode, CFG.MODES["dictation"])
        self._setup_window()
        self._setup_ui()
        self.show_all()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.set_app_paintable(True)
        self.set_decorated(False)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        if HAS_LAYER_SHELL and SESSION_TYPE == "wayland":
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_namespace(self, "linuxwhisper-recording")
            GtkLayerShell.set_exclusive_zone(self, -1)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 80)
            GtkLayerShell.set_keyboard_mode(
                self, GtkLayerShell.KeyboardMode.NONE
            )
        else:
            self.set_keep_above(True)
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            geometry = monitor.get_geometry()
            self.move((geometry.width - 500) // 2, geometry.height - 60 - 80)

        self.set_default_size(900, 50)
        geom = Gdk.Geometry()
        geom.max_height = 300
        self.set_geometry_hints(None, geom, Gdk.WindowHints.MAX_SIZE)

    def _setup_ui(self) -> None:
        """Setup label with icon and text."""
        label_text = f"{self.config['icon']}  {self.config['text']}"
        self.label = Gtk.Label(label=label_text)
        self.label.set_name("overlay-label")
        self.label.set_line_wrap(True)
        self.label.set_hexpand(True)
        self.label.set_halign(Gtk.Align.FILL)
        css = Gtk.CssProvider()
        css.load_from_data(f"""
            #overlay-label {{
                background: rgba(0, 48, 73, 0.92);
                border-radius: 15px;
                padding: 10px 25px;
                font-size: 14px;
                color: #669bbc;
            }}
        """.encode())
        style = self.label.get_style_context()
        style.add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.add(self.label)

    def set_text(self, text: str, max_chars: int = 200, is_response: bool = False) -> None:
        """Update overlay label with text (wrapped, no truncation for responses)."""
        if not is_response and len(text) > max_chars:
            text = text[:max_chars] + "…"
        self.label.set_text(text)
        css = Gtk.CssProvider()
        accent = "#10B981" if is_response else "#669bbc"
        bg = "rgba(0, 20, 40, 0.92)" if is_response else "rgba(0, 48, 73, 0.92)"
        css.load_from_data(f"""
            #overlay-label {{
                background: {bg};
                border-radius: 15px;
                padding: 10px 25px;
                font-size: 14px;
                color: {accent};
            }}
        """.encode())
        self.label.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def close(self) -> None:
        """Clean up and destroy."""
        self.destroy()
