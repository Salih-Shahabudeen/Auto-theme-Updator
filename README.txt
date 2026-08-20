THEME UPDATER GUI V12
=====================

Recommended way to open it:
  Double-click "Launch Theme Updater.bat"

You can also run:
  python Themeupdater.py

Palette modes
-------------
DEFAULT
  - Uses the fixed DEFAULT_PALETTE in color_picker.py.
  - Color fields and color-picker buttons are disabled.
  - You cannot modify Default colors from the GUI.

CUSTOM
  - Enables all five color controls.
  - Click a color swatch or "Choose Color..." to open the Windows
    color-selection dialog.
  - You can also type a #RRGGBB HEX value directly.
  - Custom colors are saved in theme_settings.json.

Applications
------------
You can choose any combination of:
  - Vivaldi
  - Simple New Tab
  - Discord / Vencord
  - VS Code
  - WezTerm
  - Spotify / Spicetify
  - Zebar
  - Windhawk Taskbar Styler

The updater keeps each application's logic in its own .py file.
WezTerm still uses the existing administrator/UAC copy method.


Portable Windows paths
----------------------
This version contains no hard-coded Windows username.

User-specific locations are resolved at runtime with:
  - Path.home()
  - %LOCALAPPDATA%
  - %APPDATA%
  - %ProgramFiles%

Resolved locations:
  Vivaldi:
    %LOCALAPPDATA%\Vivaldi\User Data\Default\Preferences

  Discord/Vencord:
    %APPDATA%\Vencord\settings\quickCss.css

  VS Code:
    %APPDATA%\Code\User\settings.json

  WezTerm:
    %ProgramFiles%\WezTerm\wezterm.lua

  Zebar:
    %APPDATA%\zebar\downloads\glzr-io.starter@0.0.0\styles.css

So the same updater can be moved to another Windows account without
editing a username in the source code.


Spotify / Spicetify
-------------------
The GUI includes a "Spotify / Spicetify" checkbox.

Portable path:
  %APPDATA%\spicetify\Themes\Starrynight\color.ini

Only [Base] is synchronized. Existing preset sections such as:
  Cotton-candy, Forest, Galaxy, Orange, Sky, and Sunrise
are preserved exactly.

The updater runs:
  spicetify apply
after writing color.ini.

Base mapping:
  star / star-glow / shooting-star -> Foreground
  main                             -> Background
  main-elevated / card             -> Window
  sidebar                          -> Accent
  sidebar-alt                      -> Background
  text / subtext                   -> Foreground
  button                           -> Accent
  button-active                    -> Highlight
  highlight                        -> Highlight
  highlight-elevated               -> Window
  player                           -> Background


Spotify fix in V6
-----------------
Spotify / Spicetify now:
  1. Updates only [Base] in Starrynight\color.ini.
  2. Finds spicetify.exe from PATH or %LOCALAPPDATA%\spicetify.
  3. Explicitly selects:
       current_theme = Starrynight
       color_scheme  = Base
  4. Enables:
       inject_css      = 1
       replace_colors  = 1
       inject_theme_js = 1
  5. Runs:
       spicetify apply

The update log shows the exact Spicetify command and any CLI error.


V7 palette precedence fix
-------------------------
Previously, theme_settings.json could override a manual edit to
CUSTOM_PALETTE in color_picker.py.

V7 detects source-code palette changes:
  - If CUSTOM_PALETTE in color_picker.py changed, that new palette wins.
  - If CUSTOM_PALETTE did not change, the most recent GUI-picked custom
    colors are restored normally.
  - Default mode remains read-only.

So editing CUSTOM_PALETTE manually and relaunching the app now updates
the GUI and all selected applications to those new values.


V8 application selection fix
----------------------------
The Apply Theme action now snapshots the checkbox states at the exact
moment you click Apply Theme.

Unchecked applications are passed to updater_core.py as excluded and
the Update Log shows both GUI selection state and core RUN/SKIP state.

Application checkboxes are temporarily disabled while an update is
running so their state cannot change mid-run.


V9 Zebar support
----------------
The GUI now includes a "Zebar" checkbox.

Portable target path:
  %APPDATA%\zebar\downloads\glzr-io.starter@0.0.0\styles.css

No Windows account name is hard-coded. If the marketplace changes the
starter pack version, the updater falls back to the newest matching
"glzr-io.starter@*" stylesheet.

Zebar palette mapping:
  Foreground  -> text
  Accent      -> icons
  Background  -> top of bar background
  Window      -> lower bar background / inactive surfaces
  Highlight   -> focused/hovered workspaces and high-usage CPU color

The updater creates a timestamped backup and writes a managed CSS override
block at the end of styles.css. Re-running the updater replaces that block
instead of stacking duplicate overrides.


V10 Windhawk Taskbar Styler support
-----------------------------------
The GUI now includes a "Windhawk Taskbar Styler" checkbox.

Registry target confirmed from the installed configuration:
  HKLM\SOFTWARE\Windhawk\Engine\Mods\windows-11-taskbar-styler\Settings

The updater changes only the color-bearing string values that were confirmed
in the existing Taskbar Styler configuration. It does not alter selectors,
font sizes, visibility rules, margins, padding, corner radii, or other layout
settings.

Palette mapping:
  Background -> taskbar/button/system-tray background surfaces
  Accent     -> running-indicator stroke states
  Foreground -> taskbar label text

Current mapped registry values:
  controlStyles[7].styles[0]   Background:=<Background>
  controlStyles[8].styles[0]   Background:=<Background>
  controlStyles[9].styles[4-8] running-indicator strokes -> <Accent>
  controlStyles[12].styles[1]  Foreground=<Foreground>
  controlStyles[16].styles[0]  Fill=<Background>
  controlStyles[18].styles[0]  Background=<Background>
  controlStyles[20].styles[0]  Background=<Background>

Before writing, the entire Taskbar Styler registry key is exported to the
local backups folder as a .reg file. The updater validates every expected
registry value first and refuses to change anything if the layout no longer
matches.

After writing settings, the updater changes SettingsChangeTime under the
parent mod key so Windhawk reloads the new settings.

Because these settings are under HKEY_LOCAL_MACHINE, selecting Windhawk
launches a small elevated PowerShell helper and Windows shows a UAC prompt.
The rest of the Theme Updater does not need to stay permanently elevated.

V12 Zebar transparency + GlazeWM restart
-----------------------------------------
Zebar now has its own Transparency slider in the GUI:
  0%   = opaque Zebar background
  100% = fully transparent Zebar background/surfaces

The slider affects Zebar background/surface alpha only. Text and icons keep
normal opacity so they remain readable. The selected transparency is saved in
theme_settings.json and restored the next time the updater opens.

When the Zebar checkbox is selected, the updater now performs this sequence:
  1. Capture the current GlazeWM executable path when possible.
  2. Close glazewm.exe.
  3. Close zebar.exe.
  4. Keep both closed while all selected theme changes are being applied.
  5. Update and back up Zebar styles.css using the selected transparency.
  6. Relaunch GlazeWM at the end, even if a later selected updater fails.
  7. Do NOT directly launch Zebar; GlazeWM's normal startup config launches it.

GlazeWM path discovery is portable and does not hard-code the Windows user:
  - current running GlazeWM process path
  - GLAZEWM_PATH environment variable
  - PATH / where resolution
  - common Program Files / LocalAppData install locations
  - versioned WinGet package folders

If Zebar is unchecked, the updater does not close or relaunch GlazeWM/Zebar.



V12 SAFE GLAZEWM/ZEBAR RESTART
------------------------------
When Zebar is selected, the updater now uses GlazeWM's own IPC shutdown first:

    glazewm.exe command wm-exit

This is preferred over force-killing the WM and allows GlazeWM to run its
configured shutdown_commands. The updater then explicitly verifies that both
GlazeWM and Zebar are stopped before styles.css is touched.

If the WM cannot be stopped normally, taskkill is attempted. If Windows denies
access, the updater requests UAC for only the short process-close operation.
If either process is still alive after that, the Zebar update is aborted rather
than editing the file while the bar/WM is active.

After the update, GlazeWM is started with the supported `glazewm.exe start`
command. Zebar itself is NOT started directly; GlazeWM's startup_commands is
expected to launch it. The updater checks for an already-running GlazeWM first
to avoid duplicate instances.
