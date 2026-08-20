r"""Spicetify / Starrynight theme updater.

Updates only the [Base] section in:
    %APPDATA%\spicetify\Themes\Starrynight\color.ini

Then explicitly configures Spicetify to use:
    current_theme = Starrynight
    color_scheme  = Base

Other color schemes in color.ini remain untouched.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from color_picker import PALETTE, SEMANTIC
from common import backup_file


APPDATA = Path(
    os.environ.get(
        "APPDATA",
        Path.home() / "AppData" / "Roaming",
    )
)

LOCALAPPDATA = Path(
    os.environ.get(
        "LOCALAPPDATA",
        Path.home() / "AppData" / "Local",
    )
)

SPICETIFY_THEME_DIR = (
    APPDATA
    / "spicetify"
    / "Themes"
    / "Starrynight"
)

SPICETIFY_COLOR_INI = SPICETIFY_THEME_DIR / "color.ini"


def _without_hash(hex_color):
    return hex_color.lstrip("#").upper()


def _replace_ini_key(section_text, key, value):
    """Replace one key while preserving spacing and anything after the value."""
    pattern = re.compile(
        rf"(?mi)^"
        rf"(?P<prefix>[ \t]*{re.escape(key)}[ \t]*=[ \t]*)"
        rf"(?P<value>[0-9A-Fa-f]{{6}})"
        rf"(?P<suffix>[^\r\n]*)$"
    )

    def repl(match):
        return (
            match.group("prefix")
            + value
            + match.group("suffix")
        )

    return pattern.subn(repl, section_text, count=1)


def _find_spicetify_exe():
    """Find Spicetify even when a GUI launch does not inherit the latest PATH."""
    from_path = shutil.which("spicetify")
    if from_path:
        return str(from_path)

    candidates = [
        # Current official Windows installer location.
        LOCALAPPDATA / "spicetify" / "spicetify.exe",

        # Older/default legacy location.
        Path.home() / "spicetify-cli" / "spicetify.exe",

        # Keep this fallback for unusual/manual installs.
        APPDATA / "spicetify" / "spicetify.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def _run_spicetify(spicetify_exe, *args):
    command = [spicetify_exe, *args]

    print()
    print("Running:")
    print("  spicetify " + " ".join(args))

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if stdout:
        print(stdout)

    if stderr:
        print(stderr)

    if result.returncode != 0:
        raise RuntimeError(
            "Spicetify command failed:\n"
            f"  spicetify {' '.join(args)}\n"
            f"Exit code: {result.returncode}\n"
            f"{stderr or stdout or 'No additional output.'}"
        )

    return stdout


def update_spicetify():
    if not SPICETIFY_THEME_DIR.exists():
        raise FileNotFoundError(
            "Starrynight theme folder not found:\n"
            f"  {SPICETIFY_THEME_DIR}"
        )

    if not SPICETIFY_COLOR_INI.exists():
        raise FileNotFoundError(
            "Starrynight color.ini not found:\n"
            f"  {SPICETIFY_COLOR_INI}"
        )

    backup_file(
        SPICETIFY_COLOR_INI,
        "spicetify_starrynight_color",
    )

    text = SPICETIFY_COLOR_INI.read_text(
        encoding="utf-8",
    )

    base_match = re.search(
        r"(?ms)^\[Base\][ \t]*\r?\n"
        r"(?P<body>.*?)"
        r"(?=^\[[^\]]+\][ \t]*\r?$|\Z)",
        text,
    )

    if not base_match:
        raise RuntimeError(
            "Could not find the [Base] section in Starrynight color.ini."
        )

    body = base_match.group("body")

    accent = _without_hash(PALETTE["accent"])
    background = _without_hash(PALETTE["background"])
    foreground = _without_hash(PALETTE["foreground"])
    highlight = _without_hash(PALETTE["highlight"])
    window = _without_hash(PALETTE["window"])

    mapping = {
        "star": foreground,
        "star-glow": foreground,
        "shooting-star": foreground,
        "shooting-star-glow": foreground,

        "main": background,
        "main-elevated": window,
        "card": window,

        "sidebar": accent,
        "sidebar-alt": background,

        "text": foreground,
        "subtext": foreground,

        "button-active": highlight,
        "button": accent,
        "button-disabled": window,

        "highlight": highlight,
        "highlight-elevated": window,

        "shadow": background,
        "selected-row": foreground,
        "misc": window,

        "notification-error": _without_hash(SEMANTIC["red"]),
        "notification": _without_hash(SEMANTIC["green"]),

        "tab-active": highlight,
        "player": background,
    }

    missing = []

    for key, value in mapping.items():
        body, count = _replace_ini_key(body, key, value)
        if count == 0:
            missing.append(key)

    if missing:
        raise RuntimeError(
            "The Starrynight [Base] section is missing expected keys:\n  "
            + "\n  ".join(missing)
        )

    updated_text = (
        text[:base_match.start("body")]
        + body
        + text[base_match.end("body"):]
    )

    temporary = SPICETIFY_COLOR_INI.with_suffix(".tmp")
    temporary.write_text(updated_text, encoding="utf-8")
    temporary.replace(SPICETIFY_COLOR_INI)

    print("Spicetify Starrynight [Base] colors updated:")
    print(f"  {SPICETIFY_COLOR_INI}")

    spicetify_exe = _find_spicetify_exe()

    if not spicetify_exe:
        raise FileNotFoundError(
            "Could not find spicetify.exe.\n"
            "Checked PATH and:\n"
            f"  {LOCALAPPDATA / 'spicetify' / 'spicetify.exe'}\n"
            f"  {Path.home() / 'spicetify-cli' / 'spicetify.exe'}"
        )

    print("Spicetify executable:")
    print(f"  {spicetify_exe}")

    # Make sure the file we just edited is the theme/scheme Spicetify will use.
    # Also ensure the Starrynight CSS, colors and theme JS are enabled.
    _run_spicetify(
        spicetify_exe,
        "config",
        "current_theme",
        "Starrynight",
        "color_scheme",
        "Base",
        "inject_css",
        "1",
        "replace_colors",
        "1",
        "inject_theme_js",
        "1",
    )

    # Apply the selected local theme. Spicetify handles Spotify restart/reload.
    _run_spicetify(
        spicetify_exe,
        "apply",
    )

    print()
    print("Spotify / Spicetify theme applied successfully.")
