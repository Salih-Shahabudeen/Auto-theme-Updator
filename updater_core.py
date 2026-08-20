"""Orchestration for selected theme updaters."""

from color_picker import PALETTE
from discord import update_discord
from simple_new_tab import update_simple_new_tab
from spicetify import update_spicetify
from vivaldi import close_vivaldi, relaunch_vivaldi, update_vivaldi
from vscode import update_vscode
from wezterm import update_wezterm

APP_KEYS = (
    "vivaldi",
    "simple_new_tab",
    "discord",
    "vscode",
    "wezterm",
    "spicetify",
)


def run_updates(selected):
    """Run only the selected applications.

    selected may be any iterable containing APP_KEYS.
    """

    selected = frozenset(selected)

    unknown = selected.difference(APP_KEYS)
    if unknown:
        raise ValueError("Unknown application(s): " + ", ".join(sorted(unknown)))

    if not selected:
        raise ValueError("Select at least one application to update.")

    print("=" * 60)
    print("ACTIVE PALETTE")
    print("=" * 60)
    for name, value in PALETTE.items():
        print(f"{name:<12} {value}")

    print()
    print("=" * 60)
    print("UPDATING THEMES")
    print("=" * 60)

    print("Selection received by updater core:")
    for key in APP_KEYS:
        print(f"  {'RUN ' if key in selected else 'SKIP'} {key}")
    print()

    browser_work = bool({"vivaldi", "simple_new_tab"} & selected)

    if browser_work:
        vivaldi_was_running = close_vivaldi()
        try:
            if "vivaldi" in selected:
                update_vivaldi()
            if "simple_new_tab" in selected:
                update_simple_new_tab()
        finally:
            relaunch_vivaldi(vivaldi_was_running)

    if "discord" in selected:
        update_discord()

    if "vscode" in selected:
        update_vscode()

    if "wezterm" in selected:
        update_wezterm()

    if "spicetify" in selected:
        update_spicetify()

    labels = {
        "vivaldi": "Vivaldi",
        "simple_new_tab": "Simple New Tab",
        "discord": "Discord/Vencord",
        "vscode": "VS Code",
        "wezterm": "WezTerm",
        "spicetify": "Spotify / Spicetify",
    }

    print()
    print("Finished:")
    for key in APP_KEYS:
        if key in selected:
            print(f"  - {labels[key]}")
