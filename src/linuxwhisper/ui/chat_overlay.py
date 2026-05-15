"""
Chat overlay using plain GTK widgets.

On Wayland: uses gtk-layer-shell for proper overlay anchoring (right edge).
On X11: uses classic GTK window hints with free positioning + drag.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

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

# Use layer-shell only on Wayland when available
USE_LAYER_SHELL = HAS_LAYER_SHELL and SESSION_TYPE == "wayland"


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
def _hex_to_rgba(hex_str: str, alpha: float) -> tuple:
    h = hex_str.lstrip('#')
    rgb = tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return (*rgb, alpha)

def _get_contrast_text(bg_hex: str) -> str:
    h = bg_hex.lstrip('#')
    rgb = [int(h[i:i+2], 16) for i in (0, 2, 4)]
    lum = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
    return "#000000" if lum > 0.5 else "#FFFFFF"

def _hex_to_css(hex_str: str) -> str:
    return f"#{hex_str.lstrip('#')}"

MSG_CSS = """
#msg-user {{
    background: {accent};
    color: {text_on_accent};
    border-radius: 12px 12px 12px 4px;
    padding: 8px 14px;
    margin: 4px 12px 4px 40px;
    font-size: 13px;
}}
#msg-assistant {{
    background: {surface};
    color: {text};
    border-radius: 12px 12px 4px 12px;
    padding: 8px 14px;
    margin: 4px 40px 4px 12px;
    font-size: 13px;
}}
window {{
    background-color: {bg};
}}
"""
class ChatOverlay(Gtk.Window):
    """Chat overlay using plain GTK widgets."""

    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._setup_window()
        self._setup_ui()
        self._init_animation()
        self.show_all()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        w, h = 380, 600

        if USE_LAYER_SHELL:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_namespace(self, "linuxwhisper-chat")
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, False)
            GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, False)
            GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 20)
            GtkLayerShell.set_keyboard_mode(
                self, GtkLayerShell.KeyboardMode.ON_DEMAND
            )
        else:
            self.set_keep_above(True)
            self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            geometry = monitor.get_geometry()
            x = geometry.x + geometry.width - w - 20
            y = geometry.y + (geometry.height - h) // 2
            self.move(x, y)

        self.set_default_size(w, h)
        self.set_size_request(w, h)

    def _setup_ui(self) -> None:
        """Setup scrolled message list with styled labels."""
        self._apply_css()

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_size_request(340, 450)

        self.msg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.msg_box.set_margin_top(12)
        self.msg_box.set_margin_bottom(12)
        self.scroll.add(self.msg_box)

        self.add(self.scroll)

    def _apply_css(self) -> None:
        """Apply dynamic CSS based on current color scheme."""
        scheme = CFG.COLOR_SCHEMES.get(STATE.color_scheme, CFG.COLOR_SCHEMES[CFG.DEFAULT_SCHEME])
        accent = _hex_to_css(scheme["accent"])
        surface = _hex_to_css(scheme["surface"])
        text = _hex_to_css(scheme["text"])
        text_on_accent = _get_contrast_text(scheme["accent"])

        bg = _hex_to_css(scheme["bg"])

        css_str = MSG_CSS.format(
            accent=accent,
            surface=surface,
            text=text,
            text_on_accent=text_on_accent,
            bg=bg,
        )

        provider = Gtk.CssProvider()
        provider.load_from_data(css_str.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _add_message_label(self, role: str, text: str) -> None:
        """Add a message bubble to the message box."""
        label = Gtk.Label(label=text)
        label.set_name(f"msg-{role}")
        label.set_line_wrap(True)
        label.set_xalign(0 if role == "assistant" else 1)
        label.set_max_width_chars(40)
        self.msg_box.pack_start(label, False, False, 0)
        self.msg_box.show_all()

    def _init_animation(self) -> None:
        """Initialize fade animation state."""
        self.opacity_value = 0.0
        self.fade_in_active = False
        self.fade_out_active = False
        self.fade_timer = None
        self.fade_callback = None
        self.start_fade_in()

    def start_fade_in(self) -> None:
        """Start fade-in animation."""
        self.fade_out_active = False
        self.fade_in_active = True
        self.opacity_value = 0.0
        self._cancel_fade_timer()
        self.fade_timer = GLib.timeout_add(16, self._fade_in_step)

    def _fade_in_step(self) -> bool:
        """Fade-in animation step."""
        self.opacity_value = min(1.0, self.opacity_value + 0.1)
        try:
            self.set_opacity(self.opacity_value)
        except Exception:
            pass
        if self.opacity_value >= 1.0:
            self.fade_in_active = False
            self.fade_timer = None
            return False
        return True

    def start_fade_out(self, callback: Optional[Callable] = None) -> None:
        """Start fade-out animation."""
        self.fade_in_active = False
        self.fade_out_active = True
        self.fade_callback = callback
        self._cancel_fade_timer()
        self.fade_timer = GLib.timeout_add(16, self._fade_out_step)

    def _fade_out_step(self) -> bool:
        """Fade-out animation step."""
        self.opacity_value = max(0.0, self.opacity_value - 0.1)
        try:
            self.set_opacity(self.opacity_value)
        except Exception:
            pass
        if self.opacity_value <= 0.0:
            self.fade_out_active = False
            self.fade_timer = None
            if self.fade_callback:
                self.fade_callback()
            return False
        return True

    def _cancel_fade_timer(self) -> None:
        """Cancel active fade timer."""
        if self.fade_timer:
            GLib.source_remove(self.fade_timer)
            self.fade_timer = None

    def update_content(self, messages: List[Dict[str, str]], status_text: Optional[str] = None,
                       is_pinned: bool = False, is_tts: bool = False) -> None:
        """Update chat messages."""
        self._apply_css()
        for child in self.msg_box.get_children():
            self.msg_box.remove(child)

        for msg in messages:
            self._add_message_label(msg["role"], msg["text"])

        if status_text:
            label = Gtk.Label(label=status_text)
            label.set_xalign(0)
            label.get_style_context().add_class("dim-label")
            self.msg_box.pack_start(label, False, False, 0)

        # Auto-scroll to bottom
        adj = self.scroll.get_vadjustment()
        if adj:
            adj.set_value(adj.get_upper() - adj.get_page_size())

        self.msg_box.show_all()

    def close(self) -> None:
        """Clean up and destroy."""
        self._cancel_fade_timer()
        self.destroy()
