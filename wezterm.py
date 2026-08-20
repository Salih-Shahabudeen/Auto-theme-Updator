"""WezTerm theme updater, including elevated writes to Program Files."""

import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from color_picker import PALETTE
from common import backup_file

WEZTERM_CONFIG = Path(r"C:\Program Files\WezTerm\wezterm.lua")

def find_lua_table_assignment_span(lua, assignment_name):
    pattern = re.compile(
        rf"(?m)^[ \t]*{re.escape(assignment_name)}[ \t]*=[ \t]*\{{"
    )
    match = pattern.search(lua)

    if not match:
        return None

    brace_start = lua.find("{", match.start())
    depth = 0
    i = brace_start
    in_single = False
    in_double = False
    escaped = False

    while i < len(lua):
        ch = lua[i]

        if escaped:
            escaped = False
            i += 1
            continue

        if ch == "\\" and (in_single or in_double):
            escaped = True
            i += 1
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue

        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue

        if not in_single and not in_double:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    while end < len(lua) and lua[end] in " \t":
                        end += 1
                    if end < len(lua) and lua[end] == "\r":
                        end += 1
                    if end < len(lua) and lua[end] == "\n":
                        end += 1
                    return match.start(), end

        i += 1

    raise RuntimeError(
        f"Found {assignment_name}, but could not find the end of its Lua table."
    )

def update_wezterm():
    if not WEZTERM_CONFIG.exists():
        raise FileNotFoundError(
            f"WezTerm config not found:\n"
            f"{WEZTERM_CONFIG}"
        )

    backup_file(WEZTERM_CONFIG, "wezterm_config")

    lua = WEZTERM_CONFIG.read_text(
        encoding="utf-8"
    )

    start_marker = "-- AUTO THEME START"
    end_marker = "-- AUTO THEME END"

    theme_block = f'''-- AUTO THEME START

config.colors = {{
    background = "{PALETTE["background"]}",

    cursor_border = "{PALETTE["accent"]}",
    cursor_bg = "{PALETTE["accent"]}",

    tab_bar = {{
        background = "{PALETTE["background"]}",

        active_tab = {{
            bg_color = "{PALETTE["background"]}",
            fg_color = "{PALETTE["highlight"]}",
            intensity = "Normal",
            underline = "None",
            italic = false,
            strikethrough = false,
        }},

        inactive_tab = {{
            bg_color = "{PALETTE["background"]}",
            fg_color = "{PALETTE["foreground"]}",
            intensity = "Normal",
            underline = "None",
            italic = false,
            strikethrough = false,
        }},

        new_tab = {{
            bg_color = "{PALETTE["background"]}",
            fg_color = "{PALETTE["foreground"]}",
        }},
    }},
}}

config.window_frame = {{
    font = wezterm.font({{
        family = "FiraMono Nerd Font",
        weight = "Regular",
    }}),

    active_titlebar_bg = "{PALETTE["background"]}",
}}

-- AUTO THEME END'''

    has_start = start_marker in lua
    has_end = end_marker in lua

    if has_start != has_end:
        raise RuntimeError(
            "WezTerm has only one AUTO THEME marker. "
            "Restore the missing marker or remove the remaining marker "
            "and run the updater again."
        )

    if has_start and has_end:
        pattern = (
            re.escape(start_marker)
            + r".*?"
            + re.escape(end_marker)
        )

        lua, count = re.subn(
            pattern,
            theme_block,
            lua,
            count=1,
            flags=re.DOTALL,
        )

        if count != 1:
            raise RuntimeError(
                "Could not replace WezTerm AUTO THEME section."
            )

        print("Existing WezTerm AUTO THEME block replaced.")

    else:
        colors_span = find_lua_table_assignment_span(
            lua,
            "config.colors",
        )

        frame_span = find_lua_table_assignment_span(
            lua,
            "config.window_frame",
        )

        spans = [
            span
            for span in (colors_span, frame_span)
            if span is not None
        ]

        if spans:
            replace_start = min(span[0] for span in spans)
            replace_end = max(span[1] for span in spans)

            lua = (
                lua[:replace_start]
                + theme_block
                + "\n\n"
                + lua[replace_end:]
            )

            print(
                "WezTerm AUTO THEME markers were missing; "
                "the existing color/window-frame configuration "
                "was converted into a managed theme block."
            )

        else:
            insertion_match = re.search(
                r"(?m)^[ \t]*config\.window_decorations[ \t]*=",
                lua,
            )

            if insertion_match is None:
                return_matches = list(
                    re.finditer(
                        r"(?m)^[ \t]*return[ \t]+config[ \t]*$",
                        lua,
                    )
                )

                insertion_match = (
                    return_matches[-1]
                    if return_matches
                    else None
                )

            if insertion_match is not None:
                lua = (
                    lua[:insertion_match.start()]
                    + theme_block
                    + "\n\n"
                    + lua[insertion_match.start():]
                )

                print(
                    "No existing WezTerm color block was found; "
                    "a managed AUTO THEME block was inserted."
                )
            else:
                if lua and not lua.endswith("\n"):
                    lua += "\n"

                lua += "\n" + theme_block + "\n"

                print(
                    "WARNING: Could not find a normal insertion point "
                    "in .wezterm.lua; AUTO THEME block was appended."
                )

    # Program Files is protected by Windows. Write the complete
    # updated config to the user's temp directory first, then launch
    # a tiny elevated PowerShell script for the final copy.
    temp_dir = Path(tempfile.gettempdir())

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    temporary = temp_dir / (
        f"wezterm_themeupdater_{timestamp}.lua"
    )

    elevate_script = temp_dir / (
        f"wezterm_themeupdater_copy_{timestamp}.ps1"
    )

    print("WezTerm config path:")
    print(f"  {WEZTERM_CONFIG}")

    try:
        temporary.write_text(
            lua,
            encoding="utf-8",
        )

        # Create a small PowerShell script that runs elevated and copies
        # the completed Lua file into Program Files.
        source_ps = str(temporary).replace("'", "''")
        target_ps = str(WEZTERM_CONFIG).replace("'", "''")

        elevate_script.write_text(
            "$ErrorActionPreference = 'Stop'\n"
            "try {\n"
            f"    Copy-Item -LiteralPath '{source_ps}' "
            f"-Destination '{target_ps}' -Force\n"
            "    exit 0\n"
            "}\n"
            "catch {\n"
            "    Write-Error $_\n"
            "    exit 1\n"
            "}\n",
            encoding="utf-8",
        )

        # Start the helper PowerShell process with the Windows 'runas'
        # verb. This is what triggers the UAC/admin prompt.
        helper_ps = str(elevate_script).replace("'", "''")

        outer_command = (
            "$p = Start-Process "
            "-FilePath 'powershell.exe' "
            "-Verb RunAs "
            "-Wait "
            "-PassThru "
            "-ArgumentList @("
            "'-NoProfile',"
            "'-ExecutionPolicy','Bypass',"
            f"'-File','{helper_ps}'"
            "); "
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
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Could not update WezTerm config in Program Files. "
                "The administrator/UAC request may have been declined "
                "or the elevated copy failed."
            )

    finally:
        for temp_path in (temporary, elevate_script):
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    print("WezTerm theme updated.")
