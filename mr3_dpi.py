"""Render at the Windows startup display DPI instead of bitmap enlargement.

Tk 8.6 uses point-sized fonts but pixel-sized layouts. Keep those pixel sizes in
96-DPI design units and scale them once. System awareness is deliberate: moving
between monitors with different scales is not dynamically supported by this UI.
"""
import ctypes
import sys

_scale = 1.0


def enable_dpi_awareness():
    """Call before creating any Tk windows; leave an existing host policy alone."""
    if sys.platform == 'win32':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # SYSTEM_DPI_AWARE
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def initialize(root):
    global _scale
    # Tk's screen-millimetre conversion can produce e.g. 144.07 for 144 DPI.
    _scale = round(root.winfo_fpixels('1i')) / 96


def dp(value):
    if isinstance(value, (tuple, list)):
        return tuple(dp(item) for item in value)
    return round(value * _scale)
