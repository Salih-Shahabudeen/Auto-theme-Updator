"""Windhawk Windows 11 Taskbar Styler palette updater.

Updates only the known color-bearing REG_SZ values in the user's existing
Taskbar Styler configuration. Layout, visibility, sizing, fonts and selectors
are left untouched. Protected HKLM writes are performed by a small elevated
PowerShell helper so the main Theme Updater doesn't need to always run as admin.
"""

import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

from color_picker import PALETTE
from common import BACKUP_DIR

MOD_ID = "windows-11-taskbar-styler"
MOD_REG_PATH = rf"SOFTWARE\Windhawk\Engine\Mods\{MOD_ID}"
SETTINGS_REG_PATH = MOD_REG_PATH + r"\Settings"
FULL_MOD_REG_PATH = rf"HKEY_LOCAL_MACHINE\{MOD_REG_PATH}"
PS_MOD_PATH = rf"Registry::HKEY_LOCAL_MACHINE\{MOD_REG_PATH}"
PS_SETTINGS_PATH = rf"Registry::HKEY_LOCAL_MACHINE\{SETTINGS_REG_PATH}"

# Exact registry value names confirmed from the user's Taskbar Styler settings.
# Only these values are changed.
COLOR_VALUE_MAP = {
    "controlStyles[7].styles[0]": ("Background:=", "background"),
    "controlStyles[8].styles[0]": ("Background:=", "background"),
    "controlStyles[9].styles[4]": ("Stroke@InactivePointerOver=", "accent"),
    "controlStyles[9].styles[5]": ("Stroke@InactivePressed=", "accent"),
    "controlStyles[9].styles[6]": ("Stroke@ActiveNormal=", "accent"),
    "controlStyles[9].styles[7]": ("Stroke@ActivePointerOver=", "accent"),
    "controlStyles[9].styles[8]": ("Stroke@ActivePressed=", "accent"),
    "controlStyles[12].styles[1]": ("Foreground=", "foreground"),
    "controlStyles[16].styles[0]": ("Fill=", "background"),
    "controlStyles[18].styles[0]": ("Background=", "background"),
    "controlStyles[20].styles[0]": ("Background=", "background"),
}


def _ps_quote(value):
    """Quote a string for a single-quoted PowerShell literal."""
    return str(value).replace("'", "''")


def _backup_registry_key():
    """Export the entire Taskbar Styler mod key before changing anything."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = BACKUP_DIR / f"windhawk_taskbar_styler_{timestamp}.reg"

    try:
        result = subprocess.run(
            ["reg.exe", "export", FULL_MOD_REG_PATH, str(backup), "/y"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Windows reg.exe was not found.") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unknown reg.exe error").strip()
        raise RuntimeError(f"Could not back up Windhawk registry settings: {detail}")

    print("Backup created:")
    print(f"  {backup}")
    return backup


def _read_and_validate():
    """Read the exact expected values before any write is attempted."""
    import winreg

    access = winreg.KEY_READ
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        access |= winreg.KEY_WOW64_64KEY

    try:
        settings_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            SETTINGS_REG_PATH,
            0,
            access,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Windhawk Windows 11 Taskbar Styler settings were not found at "
            f"HKLM\\{SETTINGS_REG_PATH}."
        ) from exc

    validated = []
    missing = []
    mismatched = []

    with settings_key:
        for value_name, (expected_prefix, palette_key) in COLOR_VALUE_MAP.items():
            try:
                current, value_type = winreg.QueryValueEx(settings_key, value_name)
            except FileNotFoundError:
                missing.append(value_name)
                continue

            if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                mismatched.append(f"{value_name} (not a string)")
                continue

            if not isinstance(current, str) or not current.startswith(expected_prefix):
                mismatched.append(
                    f"{value_name} (expected {expected_prefix!r}, found {current!r})"
                )
                continue

            validated.append((value_name, expected_prefix, palette_key, current))

    if missing or mismatched:
        details = []
        if missing:
            details.append("Missing values: " + ", ".join(missing))
        if mismatched:
            details.append("Unexpected values: " + "; ".join(mismatched))
        raise RuntimeError(
            "Windhawk Taskbar Styler settings no longer match the expected layout. "
            "No registry values were changed. " + " ".join(details)
        )

    return validated


def _run_elevated_update(validated):
    """Write settings and trigger Windhawk reload through an elevated helper."""
    temp_dir = Path(tempfile.gettempdir())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    helper = temp_dir / f"windhawk_themeupdater_{timestamp}.ps1"

    settings_ps = _ps_quote(PS_SETTINGS_PATH)
    mod_ps = _ps_quote(PS_MOD_PATH)

    lines = [
        "$ErrorActionPreference = 'Stop'",
        "try {",
    ]

    for value_name, prefix, palette_key, _old_value in validated:
        new_value = prefix + PALETTE[palette_key]
        lines.append(
            "    Set-ItemProperty "
            f"-LiteralPath '{settings_ps}' "
            f"-Name '{_ps_quote(value_name)}' "
            f"-Value '{_ps_quote(new_value)}'"
        )

    # Preserve the existing SettingsChangeTime registry type by using
    # Set-ItemProperty when it exists. If absent, create a QWORD.
    lines.extend(
        [
            f"    $modPath = '{mod_ps}'",
            "    $props = Get-ItemProperty -LiteralPath $modPath",
            "    if ($null -ne $props.SettingsChangeTime) {",
            "        $old = $props.SettingsChangeTime",
            "        if ($old -is [string]) {",
            "            $new = [DateTime]::UtcNow.Ticks.ToString()",
            "        } else {",
            "            try { $new = [Int64]$old + 1 } catch { $new = [DateTime]::UtcNow.Ticks }",
            "        }",
            "        Set-ItemProperty -LiteralPath $modPath -Name 'SettingsChangeTime' -Value $new",
            "    } else {",
            "        New-ItemProperty -LiteralPath $modPath -Name 'SettingsChangeTime' -PropertyType QWord -Value ([DateTime]::UtcNow.Ticks) -Force | Out-Null",
            "    }",
            "    exit 0",
            "} catch {",
            "    Write-Error $_",
            "    exit 1",
            "}",
        ]
    )

    helper.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        helper_ps = _ps_quote(str(helper))
        outer_command = (
            "$p = Start-Process "
            "-FilePath 'powershell.exe' "
            "-Verb RunAs "
            "-Wait "
            "-PassThru "
            "-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"
            f"'{helper_ps}'); "
            "exit $p.ExitCode"
        )

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                outer_command,
            ],
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Could not update Windhawk Taskbar Styler. The administrator/UAC "
                "request may have been declined or the elevated registry update failed."
            )
    finally:
        try:
            helper.unlink(missing_ok=True)
        except OSError:
            pass


def update_windhawk():
    if os.name != "nt":
        raise RuntimeError("Windhawk updating is only available on Windows.")

    print("Updating Windhawk Windows 11 Taskbar Styler...")
    print(f"Registry: HKLM\\{SETTINGS_REG_PATH}")

    validated = _read_and_validate()
    _backup_registry_key()

    print("Planned Windhawk color changes:")
    for value_name, prefix, palette_key, old_value in validated:
        new_value = prefix + PALETTE[palette_key]
        print(f"  {value_name}")
        print(f"    {old_value} -> {new_value}")

    _run_elevated_update(validated)

    print("Windhawk Taskbar Styler updated.")
    print("Windhawk reload signal written via SettingsChangeTime.")
