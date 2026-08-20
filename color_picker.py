"""Palette state shared by the Theme Updater GUI and all app modules.

Default mode uses DEFAULT_PALETTE exactly and is read-only in the GUI.
Custom mode uses CUSTOM_PALETTE, which can be edited through the GUI's
Windows color chooser.  PALETTE is deliberately kept as one mutable dict
so modules that import it always see the currently selected colors.
"""

import json
import math
import re
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().with_name("theme_settings.json")

DEFAULT_PALETTE = {
    "accent": "#BEA3C7",
    "background": "#0C0B0F",
    "foreground": "#F8F2F5",
    "highlight": "#BEA3C7",
    "window": "#0C0B0F",
}

CUSTOM_PALETTE = {
    "accent": "#000205",
    "background": "#6E1414",
    "foreground": "#FEFEFE",
    "highlight": "#3B1E60",
    "window": "#5454C1",
}

# Immutable snapshot of the palette written in this source file.
# This lets us detect when you manually edit CUSTOM_PALETTE later.
SOURCE_CUSTOM_PALETTE = dict(CUSTOM_PALETTE)

SEMANTIC = {
    "red": "#F38BA8",
    "green": "#A6E3A1",
    "yellow": "#F9E2AF",
}

# Keep this object alive for the lifetime of the process.
PALETTE = dict(CUSTOM_PALETTE)
USE_CUSTOM_COLORS = True

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_hex(value):
    value = value.strip()
    if not value.startswith("#"):
        value = "#" + value
    value = value.upper()
    if not _HEX_RE.fullmatch(value):
        raise ValueError(f"Invalid HEX color: {value!r}. Use #RRGGBB.")
    return value


def choose_color(parent, initial_color, title="Choose Color"):
    """Open the native Tk/Windows color chooser and return #RRGGBB or None.

    The GUI only calls this in Custom mode.  Default mode never exposes
    this function to the user.
    """
    from tkinter import colorchooser

    initial_color = normalize_hex(initial_color)
    _rgb, chosen = colorchooser.askcolor(
        color=initial_color,
        title=title,
        parent=parent,
    )

    if not chosen:
        return None

    return normalize_hex(chosen)


def validate_palette(colors):
    required = ("accent", "background", "foreground", "highlight", "window")
    missing = [name for name in required if name not in colors]
    if missing:
        raise ValueError("Missing palette colors: " + ", ".join(missing))

    return {name: normalize_hex(colors[name]) for name in required}


def save_settings():
    """Persist GUI state without hiding future manual source edits.

    `source_custom_palette` records the CUSTOM_PALETTE that existed in
    color_picker.py when the settings were saved.  On the next launch,
    if the source palette has changed, the source-code edit wins over
    the older saved GUI palette.
    """
    data = {
        "mode": "custom" if USE_CUSTOM_COLORS else "default",
        "custom_palette": CUSTOM_PALETTE,
        "source_custom_palette": SOURCE_CUSTOM_PALETTE,
    }

    SETTINGS_FILE.write_text(
        json.dumps(data, indent=4) + "\n",
        encoding="utf-8",
    )


def load_settings():
    global USE_CUSTOM_COLORS

    source_now = validate_palette(SOURCE_CUSTOM_PALETTE)

    if SETTINGS_FILE.exists():
        try:
            data = json.loads(
                SETTINGS_FILE.read_text(encoding="utf-8")
            )

            saved_source = data.get("source_custom_palette")
            saved_custom = data.get("custom_palette", {})

            source_was_manually_changed = (
                saved_source is None
                or validate_palette(saved_source) != source_now
            )

            if source_was_manually_changed:
                # A manual edit to CUSTOM_PALETTE in this Python file
                # always wins over stale theme_settings.json values.
                CUSTOM_PALETTE.clear()
                CUSTOM_PALETTE.update(source_now)
            elif saved_custom:
                # No source-code change: restore the user's most recent
                # GUI-picked custom colors.
                CUSTOM_PALETTE.clear()
                CUSTOM_PALETTE.update(
                    validate_palette(saved_custom)
                )

            USE_CUSTOM_COLORS = (
                data.get("mode", "custom") == "custom"
            )

        except Exception:
            # Invalid/stale settings should never prevent the updater
            # from using the palette defined in this source file.
            CUSTOM_PALETTE.clear()
            CUSTOM_PALETTE.update(source_now)
            USE_CUSTOM_COLORS = True

    else:
        CUSTOM_PALETTE.clear()
        CUSTOM_PALETTE.update(source_now)

    PALETTE.clear()
    PALETTE.update(
        CUSTOM_PALETTE
        if USE_CUSTOM_COLORS
        else DEFAULT_PALETTE
    )


def use_default_palette(persist=True):
    global USE_CUSTOM_COLORS
    USE_CUSTOM_COLORS = False
    PALETTE.clear()
    PALETTE.update(DEFAULT_PALETTE)
    if persist:
        save_settings()


def use_custom_palette(colors=None, persist=True):
    global USE_CUSTOM_COLORS

    if colors is not None:
        CUSTOM_PALETTE.clear()
        CUSTOM_PALETTE.update(validate_palette(colors))

    USE_CUSTOM_COLORS = True
    PALETTE.clear()
    PALETTE.update(CUSTOM_PALETTE)

    if persist:
        save_settings()


def reset_custom_palette(persist=True):
    defaults = {
        "accent": "#000205",
        "background": "#6E1414",
        "foreground": "#FEFEFE",
        "highlight": "#3B1E60",
        "window": "#5454C1",
    }
    CUSTOM_PALETTE.clear()
    CUSTOM_PALETTE.update(defaults)

    if USE_CUSTOM_COLORS:
        PALETTE.clear()
        PALETTE.update(CUSTOM_PALETTE)

    if persist:
        save_settings()


def hex_to_rgb(hex_color):
    hex_color = normalize_hex(hex_color).lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def srgb_to_linear(value):
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def hex_to_oklch(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    r = srgb_to_linear(r)
    g = srgb_to_linear(g)
    b = srgb_to_linear(b)

    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    l_ = l ** (1 / 3)
    m_ = m ** (1 / 3)
    s_ = s ** (1 / 3)

    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    C = math.sqrt(a * a + b * b)
    h = math.degrees(math.atan2(b, a))
    if h < 0:
        h += 360
    return L, C, h


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def offset_hex(hex_color, amount):
    hex_color = normalize_hex(hex_color).lstrip("#")
    channels = [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
    channels = [int(clamp(channel + amount, 0, 255)) for channel in channels]
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def oklch(hex_color, lightness=None, chroma_scale=1.0, hue_shift=0, alpha=None):
    L, C, h = hex_to_oklch(hex_color)

    if lightness is not None:
        L = lightness

    C *= chroma_scale
    h = (h + hue_shift) % 360
    L = clamp(L, 0, 1)
    C = max(0, C)
    l_percent = L * 100

    if alpha is None:
        return f"oklch({l_percent:.1f}% {C:.3f} {h:.1f})"

    return (
        f"oklch({l_percent:.1f}% {C:.3f} {h:.1f} / {alpha:.2f})"
    )


def make_ramp(source, lightness_values, chroma_scale=1.0, hue_shift=0):
    return [
        oklch(
            source,
            lightness=L,
            chroma_scale=chroma_scale,
            hue_shift=hue_shift,
        )
        for L in lightness_values
    ]


load_settings()
