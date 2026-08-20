"""Orchestration for selected theme updaters."""

from color_picker import PALETTE, normalize_zebar_transparency
from discord import update_discord
from glazewm_control import close_glazewm_and_zebar, relaunch_glazewm
from simple_new_tab import update_simple_new_tab
from spicetify import update_spicetify
from vivaldi import close_vivaldi, relaunch_vivaldi, update_vivaldi
from vscode import update_vscode
from wezterm import update_wezterm
from zebar import update_zebar
from windhawk import update_windhawk

APP_KEYS = (
    "vivaldi",
    "simple_new_tab",
    "discord",
    "vscode",
    "wezterm",
    "spicetify",
    "zebar",
    "windhawk",
)


def run_updates(selected, zebar_transparency=40):
    """Run only the selected applications.

    selected may be any iterable containing APP_KEYS.
    When Zebar is selected, GlazeWM and Zebar are stopped before any theme
    writes begin, and GlazeWM is relaunched at the end. The user's GlazeWM
    startup config is responsible for starting Zebar again.
    """

    selected = frozenset(selected)
    zebar_transparency = normalize_zebar_transparency(zebar_transparency)

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
    if "zebar" in selected:
        print(f"{'zebar transparency':<18} {zebar_transparency}%")

    print()
    print("=" * 60)
    print("UPDATING THEMES")
    print("=" * 60)

    print("Selection received by updater core:")
    for key in APP_KEYS:
        print(f"  {'RUN ' if key in selected else 'SKIP'} {key}")
    print()

    glazewm_session = None
    zebar_session = "zebar" in selected

    # Keep GlazeWM/Zebar fully stopped for the entire update session whenever
    # Zebar is being modified. Always relaunch GlazeWM in the finally block,
    # even if another selected updater fails later.
    if zebar_session:
        glazewm_session = close_glazewm_and_zebar()

    try:
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

        if "zebar" in selected:
            update_zebar(zebar_transparency)

        if "windhawk" in selected:
            update_windhawk()

    finally:
        if zebar_session:
            print()
            print("Zebar update session complete; relaunching GlazeWM...")
            relaunch_glazewm(glazewm_session)

    labels = {
        "vivaldi": "Vivaldi",
        "simple_new_tab": "Simple New Tab",
        "discord": "Discord/Vencord",
        "vscode": "VS Code",
        "wezterm": "WezTerm",
        "spicetify": "Spotify / Spicetify",
        "zebar": "Zebar",
        "windhawk": "Windhawk Taskbar Styler",
    }

    print()
    print("Finished:")
    for key in APP_KEYS:
        if key in selected:
            print(f"  - {labels[key]}")
