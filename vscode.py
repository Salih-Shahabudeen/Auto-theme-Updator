import os
"""VS Code Catppuccin theme updater."""

import json
from pathlib import Path

from color_picker import PALETTE, SEMANTIC, offset_hex
from common import backup_file

APPDATA = Path(
    os.environ.get(
        "APPDATA",
        Path.home() / "AppData" / "Roaming",
    )
)

VS_CODE_SETTINGS = (
    APPDATA
    / "Code"
    / "User"
    / "settings.json"
)

def update_vscode():
    if not VS_CODE_SETTINGS.exists():
        raise FileNotFoundError(
            f"VS Code settings.json not found:\n"
            f"{VS_CODE_SETTINGS}"
        )

    backup_file(VS_CODE_SETTINGS, "vscode_settings")

    with VS_CODE_SETTINGS.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    # Keep Catppuccin's syntax palette intact, but synchronize the
    # important theme colors with the same master palette used by
    # Vivaldi and Discord.
    #
    # "all" applies these accents across Catppuccin flavors.
    # "mocha" makes the currently selected Mocha theme OLED-black.
    data["catppuccin.colorOverrides"] = {
        "all": {
            "text": PALETTE["foreground"],
            "lavender": PALETTE["accent"],
            "mauve": PALETTE["highlight"],
            "red": SEMANTIC["red"],
            "green": SEMANTIC["green"],
            "yellow": SEMANTIC["yellow"],
        },
        "mocha": {
            "base": PALETTE["background"],
            "mantle": offset_hex(PALETTE["background"], 1),
            "crust": offset_hex(PALETTE["background"], 2),
        },
    }

    temporary = VS_CODE_SETTINGS.with_suffix(".tmp")

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False,
        )
        f.write("\n")

    temporary.replace(VS_CODE_SETTINGS)

    print("VS Code Catppuccin theme updated.")
