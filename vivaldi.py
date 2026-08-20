"""Vivaldi browser theme updater and browser process control."""

import json
import subprocess
import time
from pathlib import Path

from color_picker import PALETTE
from common import backup_file

VIVALDI_PREFERENCES = Path(
    r"C:\Users\SdSNu\AppData\Local\Vivaldi\User Data\Default\Preferences"
)
VIVALDI_EXE = VIVALDI_PREFERENCES.parents[2] / "Application" / "vivaldi.exe"
THEME_NAME = "Catppuccin Mocha Lavender Amoled"

def is_vivaldi_running():
    """Return True if any Vivaldi process is currently running."""

    result = subprocess.run(
        [
            "tasklist",
            "/FI",
            "IMAGENAME eq vivaldi.exe",
            "/NH",
        ],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    return "vivaldi.exe" in result.stdout.lower()

def close_vivaldi():
    """
    Gracefully close Vivaldi before editing Preferences.

    Editing Chromium/Vivaldi Preferences while the browser is still
    running is unsafe because Vivaldi may overwrite the file when it
    exits. CloseMainWindow asks the browser to shut down normally so
    its current session can be saved first.

    Returns True if Vivaldi was running before this function was called.
    """

    if not is_vivaldi_running():
        print("Vivaldi is not running; no restart needed.")
        return False

    print("Closing Vivaldi before updating its theme...")

    # Ask only Vivaldi processes that own a visible window to close.
    # The main browser process handles the normal shutdown sequence.
    powershell_command = (
        "Get-Process vivaldi -ErrorAction SilentlyContinue | "
        "Where-Object { $_.MainWindowHandle -ne 0 } | "
        "ForEach-Object { [void]$_.CloseMainWindow() }"
    )

    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            powershell_command,
        ],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    # Give Vivaldi time to save its session and exit normally.
    deadline = time.time() + 10

    while time.time() < deadline:
        if not is_vivaldi_running():
            print("Vivaldi closed cleanly.")
            return True

        time.sleep(0.25)

    # If a renderer/background process is stuck, force-close the
    # remaining Vivaldi process tree so Preferences can be written.
    print("Vivaldi did not fully exit; closing remaining processes...")

    subprocess.run(
        [
            "taskkill",
            "/IM",
            "vivaldi.exe",
            "/T",
            "/F",
        ],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    # Briefly wait for Windows to release the Preferences file.
    deadline = time.time() + 3

    while time.time() < deadline:
        if not is_vivaldi_running():
            break
        time.sleep(0.2)

    return True

def relaunch_vivaldi(was_running):
    """Reopen Vivaldi only if it was open before the theme update."""

    if not was_running:
        return

    if not VIVALDI_EXE.exists():
        print(
            "WARNING: Vivaldi was closed, but the executable was not found:\n"
            f"  {VIVALDI_EXE}\n"
            "Open Vivaldi manually."
        )
        return

    print("Reopening Vivaldi...")

    # Popen returns immediately and leaves Vivaldi running after this
    # updater exits. Normal Vivaldi session restoration handles tabs.
    subprocess.Popen(
        [str(VIVALDI_EXE)],
        creationflags=(
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        ),
        close_fds=True,
    )

def find_theme(obj):
    if isinstance(obj, dict):

        if obj.get("name") == THEME_NAME:
            return obj

        for value in obj.values():
            result = find_theme(value)

            if result:
                return result

    elif isinstance(obj, list):

        for item in obj:
            result = find_theme(item)

            if result:
                return result

    return None

def update_vivaldi():
    if not VIVALDI_PREFERENCES.exists():
        raise FileNotFoundError(
            f"Vivaldi Preferences not found:\n"
            f"{VIVALDI_PREFERENCES}"
        )

    backup_file(VIVALDI_PREFERENCES, "vivaldi_preferences")

    with VIVALDI_PREFERENCES.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    theme = find_theme(data)

    if theme is None:
        raise RuntimeError(
            f"Could not find Vivaldi theme: "
            f"{THEME_NAME}"
        )

    # Master palette -> Vivaldi

    theme["colorAccentBg"] = PALETTE["accent"]
    theme["colorBg"] = PALETTE["background"]
    theme["colorFg"] = PALETTE["foreground"]
    theme["colorHighlightBg"] = PALETTE["highlight"]
    theme["colorWindowBg"] = PALETTE["window"]

    # Keep the browser chrome on the fixed theme accent rather
    # than recoloring the top bar from each active webpage.
    theme["accentFromPage"] = False
    theme["accentOnWindow"] = True

    # Atomic-ish write through temporary file

    temporary = VIVALDI_PREFERENCES.with_suffix(
        ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    temporary.replace(VIVALDI_PREFERENCES)

    print("Vivaldi theme updated.")
