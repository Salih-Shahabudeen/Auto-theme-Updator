r"""Zebar starter widget theme updater.

Updates the marketplace starter stylesheet at:
    %APPDATA%\zebar\downloads\glzr-io.starter@0.0.0\styles.css

The Windows account name is never hard-coded. The location is resolved
at runtime from %APPDATA% (with Path.home() as a fallback).
"""

import os
import re
from pathlib import Path

from color_picker import PALETTE, normalize_zebar_transparency
from common import backup_file


APPDATA = Path(
    os.environ.get(
        "APPDATA",
        Path.home() / "AppData" / "Roaming",
    )
)

ZEBAR_DOWNLOADS_DIR = APPDATA / "zebar" / "downloads"
ZEBAR_STARTER_DIR = ZEBAR_DOWNLOADS_DIR / "glzr-io.starter@0.0.0"
ZEBAR_STYLES_CSS = ZEBAR_STARTER_DIR / "styles.css"

START_MARKER = "/* === AUTO THEME: ZEBAR START === */"
END_MARKER = "/* === AUTO THEME: ZEBAR END === */"


def _hex_channels(hex_color):
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_css(hex_color, alpha=None):
    r, g, b = _hex_channels(hex_color)
    if alpha is None:
        return f"rgb({r} {g} {b})"
    return f"rgb({r} {g} {b} / {alpha})"


def _surface_alpha(base_percent, transparency_percent):
    """Scale surface opacity while leaving text/icon opacity untouched."""
    transparency = normalize_zebar_transparency(transparency_percent)
    visible_fraction = 1.0 - (transparency / 100.0)
    alpha = round(base_percent * visible_fraction)
    return f"{max(0, min(100, alpha))}%"


def _managed_block(transparency_percent):
    """Build the CSS override block from the active synchronized palette."""
    transparency = normalize_zebar_transparency(transparency_percent)

    accent = PALETTE["accent"]
    background = PALETTE["background"]
    foreground = PALETTE["foreground"]
    highlight = PALETTE["highlight"]
    window = PALETTE["window"]

    # The slider represents transparency, not opacity:
    # 0% transparency -> fully opaque main bar.
    # 100% transparency -> fully transparent main bar/surfaces.
    root_alpha = f"{100 - transparency}%"

    return f"""{START_MARKER}
/*
 * Managed by Theme Updater.
 * Zebar transparency: {transparency}%
 * Edit the palette/transparency in the updater instead of this block manually.
 */
:root {{
  --text-color-light: {_rgb_css(foreground, '95%')};
  --text-color-dark: {_rgb_css(foreground, '95%')};

  --icon-color-light: {_rgb_css(accent, '95%')};
  --icon-color-dark: {_rgb_css(accent, '95%')};

  --background-color-light: linear-gradient(
    {_rgb_css(background, root_alpha)},
    {_rgb_css(window, root_alpha)}
  );
  --background-color-dark: linear-gradient(
    {_rgb_css(background, root_alpha)},
    {_rgb_css(window, root_alpha)}
  );
}}

#root {{
  border-bottom-color: {_rgb_css(foreground, _surface_alpha(7, transparency))};
}}

.workspace {{
  background: {_rgb_css(window, _surface_alpha(22, transparency))};
  color: {_rgb_css(foreground, '95%')};
}}

.workspace.displayed {{
  background: {_rgb_css(window, _surface_alpha(42, transparency))};
}}

.workspace.focused,
.workspace:hover {{
  background: {_rgb_css(highlight, _surface_alpha(68, transparency))};
}}

.binding-mode,
.tiling-direction,
.paused-button {{
  background: {_rgb_css(window, _surface_alpha(42, transparency))};
  color: {_rgb_css(foreground, '95%')};
}}

.cpu .high-usage {{
  color: {_rgb_css(highlight)};
}}
{END_MARKER}"""


def _find_stylesheet():
    """Return the requested starter stylesheet, with a safe version fallback."""
    if ZEBAR_STYLES_CSS.exists():
        return ZEBAR_STYLES_CSS

    # Marketplace pack versions can change. If 0.0.0 no longer exists,
    # use the newest matching starter download instead of embedding a username.
    candidates = sorted(
        ZEBAR_DOWNLOADS_DIR.glob("glzr-io.starter@*/styles.css"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "Zebar starter styles.css was not found. Expected:\n"
        "  %APPDATA%\\zebar\\downloads\\glzr-io.starter@0.0.0\\styles.css"
    )


def update_zebar(transparency_percent=40):
    transparency = normalize_zebar_transparency(transparency_percent)
    path = _find_stylesheet()

    backup_file(path, "zebar_starter_styles")

    text = path.read_text(encoding="utf-8")
    block = _managed_block(transparency)

    marker_pattern = re.compile(
        re.escape(START_MARKER)
        + r".*?"
        + re.escape(END_MARKER),
        flags=re.DOTALL,
    )

    if marker_pattern.search(text):
        updated = marker_pattern.sub(block, text, count=1)
    else:
        updated = text.rstrip() + "\n\n" + block + "\n"

    path.write_text(updated, encoding="utf-8")

    print("Zebar starter theme updated.")
    print(f"  Transparency: {transparency}%")
    print("  %APPDATA%\\zebar\\downloads\\glzr-io.starter@...\\styles.css")
