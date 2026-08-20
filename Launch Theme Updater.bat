@echo off
cd /d "%~dp0"
where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw.exe "%~dp0ThemeUpdater.pyw"
) else (
    python "%~dp0Themeupdater.py"
)
