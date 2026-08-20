"""Shared backup helpers used by the application-specific updaters."""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKUP_DIR = SCRIPT_DIR / "backups"

def backup_file(path, label):
    """
    Save timestamped backups inside the backups folder beside
    this script. This remains stable even when launched by a
    shortcut or Windows Task Scheduler.
    """

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_")

    extension = path.suffix
    if extension:
        backup = BACKUP_DIR / f"{safe_label}_{timestamp}{extension}.bak"
    else:
        backup = BACKUP_DIR / f"{safe_label}_{timestamp}.bak"

    shutil.copy2(path, backup)

    print("Backup created:")
    print(f"  {backup}")

def backup_json_value(label, value):
    """Back up a non-file JSON value beside the script."""

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_")
    backup = BACKUP_DIR / f"{safe_label}_{timestamp}.json.bak"

    with backup.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=4, ensure_ascii=False)
        f.write("\n")

    print("Backup created:")
    print(f"  {backup}")

def backup_directory_zip(path, label):
    """Create a timestamped ZIP backup of a directory beside the script."""

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_")
    archive_base = BACKUP_DIR / f"{safe_label}_{timestamp}"

    archive = shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=path.parent,
        base_dir=path.name,
    )

    print("Backup created:")
    print(f"  {archive}")
