"""Discord/Vencord QuickCSS theme updater."""

import re
from pathlib import Path

from color_picker import PALETTE, SEMANTIC, make_ramp, oklch
from common import backup_file

DISCORD_THEME = Path(
    r"C:\Users\SdSNu\AppData\Roaming\Vencord\settings\quickCss.css"
)

def generate_discord_colors():
    accent = PALETTE["accent"]
    background = PALETTE["background"]
    foreground = PALETTE["foreground"]
    highlight = PALETTE["highlight"]
    window = PALETTE["window"]

    # Main accent ramps. Keep neutral background/window colors out
    # of the chromatic ramps so Discord accents stay vivid.
    purple = make_ramp(
        highlight,
        [0.84, 0.78, 0.71, 0.64, 0.56],
        chroma_scale=1.00,
    )

    lavender = make_ramp(
        accent,
        [0.90, 0.84, 0.77, 0.69, 0.61],
        chroma_scale=0.90,
    )

    # Derive a cooler blue from the lavender accent.
    blue = make_ramp(
        accent,
        [0.84, 0.78, 0.72, 0.65, 0.58],
        chroma_scale=1.05,
        hue_shift=-24,
    )

    # Derive a warmer pink from the mauve highlight.
    pink = make_ramp(
        highlight,
        [0.84, 0.78, 0.71, 0.64, 0.57],
        chroma_scale=0.95,
        hue_shift=28,
    )

    # Semantic colors use dedicated Catppuccin sources instead of
    # rotating the lavender accent.  This keeps red actually red/pink,
    # green actually green, and yellow actually yellow on true black.
    red = make_ramp(
        SEMANTIC["red"],
        [0.82, 0.76, 0.70, 0.64, 0.58],
        chroma_scale=1.00,
    )

    green = make_ramp(
        SEMANTIC["green"],
        [0.84, 0.78, 0.72, 0.66, 0.60],
        chroma_scale=1.00,
    )

    yellow = make_ramp(
        SEMANTIC["yellow"],
        [0.88, 0.82, 0.76, 0.70, 0.64],
        chroma_scale=1.00,
    )

    colors = {
        # ----------------------------------------------------
        # Text
        # ----------------------------------------------------

        "text-0": oklch(
            background,
            lightness=0.18,
            chroma_scale=0.30,
        ),

        "text-1": oklch(
            foreground,
            lightness=0.96,
            chroma_scale=0,
        ),

        "text-2": oklch(
            foreground,
            lightness=0.90,
            chroma_scale=0,
        ),

        "text-3": oklch(
            foreground,
            lightness=0.82,
            chroma_scale=0,
        ),

        "text-4": oklch(
            window,
            lightness=0.67,
            chroma_scale=0.20,
        ),

        "text-5": oklch(
            window,
            lightness=0.50,
            chroma_scale=0.15,
        ),

        # ----------------------------------------------------
        # Backgrounds
        # ----------------------------------------------------

        # Keep Discord genuinely AMOLED-black.  Previously these
        # values forced fixed OKLCH lightness levels, meaning even
        # #000000 was converted back into dark gray.  Backgrounds
        # now use only the neutral master colors.

        # Elevated/popout surface: still very dark, but visible
        # against the true-black base.
        "bg-1": oklch(
            window,
            lightness=0.20,
            chroma_scale=0.25,
        ),

        # Sidebar / secondary surface: preserve the exact window
        # color instead of tinting it with the purple highlight.
        "bg-2": oklch(
            window,
            chroma_scale=0.25,
        ),

        # Main surfaces use the exact HEX master background.
        # No color-space conversion is applied, so #000000 stays
        # literal #000000 and cannot influence any chromatic ramp.
        "bg-3": background,
        "bg-4": background,

        # ----------------------------------------------------
        # Interaction
        # ----------------------------------------------------

        "hover": oklch(
            accent,
            lightness=0.70,
            chroma_scale=0.75,
            alpha=0.10,
        ),

        "active": oklch(
            accent,
            lightness=0.70,
            chroma_scale=0.75,
            alpha=0.18,
        ),

        "active-2": oklch(
            accent,
            lightness=0.70,
            chroma_scale=0.75,
            alpha=0.28,
        ),

        "message-hover": oklch(
            accent,
            lightness=0.70,
            chroma_scale=0.75,
            alpha=0.07,
        ),

        # ----------------------------------------------------
        # Borders
        # ----------------------------------------------------

        "border-light": oklch(
            accent,
            lightness=0.75,
            chroma_scale=0.55,
            alpha=0.08,
        ),

        "border": oklch(
            accent,
            lightness=0.75,
            chroma_scale=0.55,
            alpha=0.18,
        ),

        "button-border": oklch(
            window,
            lightness=0.85,
            chroma_scale=0.40,
            alpha=0.12,
        ),
    }

    # Add generated ramps

    for i, value in enumerate(purple, 1):
        colors[f"purple-{i}"] = value

    for i, value in enumerate(lavender, 1):
        colors[f"lavender-{i}"] = value

    for i, value in enumerate(pink, 1):
        colors[f"pink-{i}"] = value

    for i, value in enumerate(red, 1):
        colors[f"red-{i}"] = value

    for i, value in enumerate(green, 1):
        colors[f"green-{i}"] = value

    for i, value in enumerate(blue, 1):
        colors[f"blue-{i}"] = value

    for i, value in enumerate(yellow, 1):
        colors[f"yellow-{i}"] = value

    return colors

def update_css_variable(css, name, value):
    pattern = (
        rf"(?m)^"
        rf"(\s*--{re.escape(name)}\s*:\s*)"
        rf"[^;]*"
        rf"(;)"
    )

    def replacement(match):
        return (
            f"{match.group(1)}"
            f"{value}"
            f"{match.group(2)}"
        )

    return re.subn(
        pattern,
        replacement,
        css,
        count=1,
    )

def update_discord():
    if not DISCORD_THEME.exists():
        raise FileNotFoundError(
            f"Discord theme not found:\n"
            f"{DISCORD_THEME}"
        )

    backup_file(DISCORD_THEME, "vencord_quickcss")

    css = DISCORD_THEME.read_text(
        encoding="utf-8"
    )

    colors = generate_discord_colors()

    updated = []
    missing = []

    for name, value in colors.items():

        css, count = update_css_variable(
            css,
            name,
            value,
        )

        if count:
            updated.append(name)
        else:
            missing.append(name)

    DISCORD_THEME.write_text(
        css,
        encoding="utf-8",
    )

    print(
        f"Discord theme updated "
        f"({len(updated)} variables)."
    )

    if missing:
        print()
        print("Variables not found in CSS:")

        for name in missing:
            print(f"  --{name}")
