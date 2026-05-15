from __future__ import annotations
from dataclasses import dataclass

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk


@dataclass
class OverlaySizing:
    width: int
    height: int


def get_monitor_geometry() -> tuple[int, int, int, int]:
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor() or display.get_monitor(0)
    geom = monitor.get_geometry()
    return geom.x, geom.y, geom.width, geom.height


def recording_sizing(monitor_w: int, monitor_h: int) -> OverlaySizing:
    w = max(350, min(int(monitor_w * 0.65), 1000))
    return OverlaySizing(width=w, height=-1)


def chat_sizing(monitor_w: int, monitor_h: int) -> OverlaySizing:
    w = max(280, min(int(monitor_w * 0.22), 440))
    h = max(400, min(int(monitor_h * 0.85), 900))
    return OverlaySizing(width=w, height=h)
