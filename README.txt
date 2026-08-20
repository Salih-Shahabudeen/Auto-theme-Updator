THEME UPDATER GUI V3
====================

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
