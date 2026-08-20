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
