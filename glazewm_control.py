"""Safely stop GlazeWM/Zebar for theme edits and restart GlazeWM afterwards.

GlazeWM is asked to shut down through its own IPC command first. This is much
safer than force-killing the WM because it lets GlazeWM run shutdown_commands
(and therefore lets the user's normal Zebar shutdown behavior run too).

If graceful shutdown fails, a normal taskkill is attempted, followed by an
administrator/UAC taskkill only when required. Theme writes must not begin
until both GlazeWM and Zebar are confirmed stopped.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _run_quiet(command, timeout=15):
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        class TimeoutResult:
            returncode = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or "Command timed out."
        return TimeoutResult()


def _process_running(image_name):
    """Return True when at least one process with image_name is still alive."""
    if os.name != "nt":
        return False

    stem = Path(image_name).stem
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            f"if (Get-Process -Name '{stem}' -ErrorAction SilentlyContinue) "
            "{ exit 0 } else { exit 1 }"
        ),
    ]
    return _run_quiet(command, timeout=5).returncode == 0


def _wait_until_stopped(image_name, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_running(image_name):
            return True
        time.sleep(0.15)
    return not _process_running(image_name)


def _registry_install_dir():
    """Read the MSI install directory when available."""
    if os.name != "nt":
        return None

    result = _run_quiet(
        [
            "reg.exe",
            "query",
            r"HKLM\SOFTWARE\glzr.io\GlazeWM",
            "/v",
            "InstallDir",
        ],
        timeout=5,
    )
    if result.returncode != 0:
        return None

    # REG query output is whitespace-separated. Keep the remainder after REG_SZ.
    for line in result.stdout.splitlines():
        if "InstallDir" in line and "REG_" in line:
            parts = line.split("REG_SZ", 1)
            if len(parts) == 2:
                value = parts[1].strip().strip('"')
                if value:
                    return Path(os.path.expandvars(value))
    return None


def _running_main_path():
    """Try to read the executable path of the currently running WM process."""
    if os.name != "nt":
        return None

    # Accessing Path can fail when the running WM has a higher integrity level,
    # so this is only one discovery source and never the only one.
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        (
            "$p = Get-Process -Name glazewm -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Path -and $_.Path -notmatch '\\\\cli\\\\glazewm\\.exe$' } | "
            "Select-Object -First 1; "
            "if ($p -and $p.Path) { [Console]::Out.Write($p.Path) }"
        ),
    ]
    result = _run_quiet(command, timeout=5)
    candidate = result.stdout.strip()
    if candidate:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def _main_from_cli(cli_path):
    if not cli_path:
        return None
    path = Path(cli_path)
    if path.parent.name.lower() == "cli":
        candidate = path.parent.parent / "glazewm.exe"
        if candidate.exists():
            return candidate
    return None


def find_glazewm_cli():
    """Find the GlazeWM CLI used for `command wm-exit` and `start`."""
    if os.name != "nt":
        return None

    env_hint = os.environ.get("GLAZEWM_CLI_PATH")
    if env_hint:
        hint = Path(os.path.expandvars(env_hint))
        if hint.exists():
            return hint

    which = shutil.which("glazewm.exe") or shutil.which("glazewm")
    if which:
        path = Path(which)
        # MSI installs normally put the CLI in a `cli` folder and add it to PATH.
        if path.exists():
            return path

    install_dir = _registry_install_dir()
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    local_appdata = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )

    candidates = []
    if install_dir:
        candidates.extend(
            [
                install_dir / "cli" / "glazewm.exe",
                install_dir / "glazewm.exe",
            ]
        )

    candidates.extend(
        [
            program_files / "glzr.io" / "GlazeWM" / "cli" / "glazewm.exe",
            program_files / "glzr.io" / "cli" / "glazewm.exe",
            program_files / "GlazeWM" / "cli" / "glazewm.exe",
            local_appdata / "Programs" / "glzr.io" / "GlazeWM" / "cli" / "glazewm.exe",
            local_appdata / "Programs" / "GlazeWM" / "cli" / "glazewm.exe",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    winget_packages = local_appdata / "Microsoft" / "WinGet" / "Packages"
    if winget_packages.exists():
        matches = list(winget_packages.glob("*glazewm*/**/glazewm.exe"))
        # Prefer a path explicitly inside `cli` for IPC commands.
        matches.sort(
            key=lambda p: (
                p.parent.name.lower() == "cli",
                p.stat().st_mtime if p.exists() else 0,
            ),
            reverse=True,
        )
        if matches:
            return matches[0]

    return None


def find_glazewm_main(path_hint=None):
    """Resolve the actual WM executable, not merely the CLI executable."""
    if os.name != "nt":
        return None

    if path_hint:
        hint = Path(path_hint)
        if hint.exists():
            main = _main_from_cli(hint)
            return main or hint

    env_hint = os.environ.get("GLAZEWM_PATH")
    if env_hint:
        hint = Path(os.path.expandvars(env_hint))
        if hint.exists():
            main = _main_from_cli(hint)
            return main or hint

    running = _running_main_path()
    if running:
        return running

    install_dir = _registry_install_dir()
    if install_dir:
        candidate = install_dir / "glazewm.exe"
        if candidate.exists():
            return candidate

    cli = find_glazewm_cli()
    main = _main_from_cli(cli)
    if main:
        return main

    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    local_appdata = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    candidates = [
        program_files / "glzr.io" / "GlazeWM" / "glazewm.exe",
        program_files / "glzr.io" / "glazewm.exe",
        program_files / "GlazeWM" / "glazewm.exe",
        local_appdata / "Programs" / "glzr.io" / "GlazeWM" / "glazewm.exe",
        local_appdata / "Programs" / "GlazeWM" / "glazewm.exe",
        local_appdata / "GlazeWM" / "glazewm.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _taskkill(image_name):
    result = _run_quiet(["taskkill.exe", "/IM", image_name, "/F", "/T"], timeout=10)
    if result.returncode == 0:
        return True, (result.stdout or "").strip()
    detail = (result.stderr or result.stdout or "taskkill failed").strip()
    return False, detail


def _elevated_taskkill(image_names):
    """Request UAC once and kill the supplied process image names."""
    if not image_names:
        return True

    # The PowerShell instance itself is non-elevated; Start-Process asks Windows
    # for elevation only for the short-lived taskkill helper.
    taskkill_args = []
    for image_name in image_names:
        taskkill_args.extend(["/IM", image_name])
    taskkill_args.extend(["/F", "/T"])

    ps_args = ",".join("'" + arg.replace("'", "''") + "'" for arg in taskkill_args)
    command = (
        "$p = Start-Process -FilePath 'taskkill.exe' -Verb RunAs -Wait -PassThru "
        f"-ArgumentList @({ps_args}); exit $p.ExitCode"
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        check=False,
        creationflags=CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def _graceful_glazewm_exit(cli_path):
    if not cli_path or not Path(cli_path).exists():
        print("GlazeWM CLI was not found; skipping graceful wm-exit command.")
        return False

    print(f"Requesting clean GlazeWM shutdown via: {cli_path} command wm-exit")
    result = _run_quiet([str(cli_path), "command", "wm-exit"], timeout=10)
    if result.returncode == 0:
        if _wait_until_stopped("glazewm.exe", timeout=4.0):
            print("GlazeWM closed cleanly through wm-exit.")
            return True
        print("GlazeWM accepted wm-exit but is still running after the wait period.")
        return False

    detail = (result.stderr or result.stdout or "unknown CLI error").strip()
    print(f"GlazeWM wm-exit command failed: {detail}")
    return False


def _ensure_process_stopped(image_name, friendly_name):
    """Stop a process and verify it is actually gone."""
    if not _process_running(image_name):
        print(f"{friendly_name} is already stopped.")
        return True

    print(f"Stopping {friendly_name}...")
    killed, detail = _taskkill(image_name)
    if killed and _wait_until_stopped(image_name, timeout=2.5):
        print(f"{friendly_name} stopped.")
        return True

    if detail:
        print(f"Normal process close failed: {detail}")

    print(f"Requesting administrator permission to stop {friendly_name}...")
    if _elevated_taskkill([image_name]) and _wait_until_stopped(image_name, timeout=3.0):
        print(f"{friendly_name} stopped with administrator permission.")
        return True

    return not _process_running(image_name)


def close_glazewm_and_zebar():
    """Stop both programs and return information needed for restart.

    No theme modification should proceed unless this function returns
    successfully. A failure raises RuntimeError, preventing the updater from
    writing Zebar's CSS while either program is still active.
    """
    if os.name != "nt":
        print("Skipping GlazeWM/Zebar process control outside Windows.")
        return {"cli": None, "main": None, "was_running": False}

    cli_path = find_glazewm_cli()
    main_path = find_glazewm_main()
    was_running = _process_running("glazewm.exe")

    print("Preparing Zebar update: closing GlazeWM and Zebar...")
    if cli_path:
        print(f"GlazeWM CLI: {cli_path}")
    if main_path:
        print(f"GlazeWM main executable: {main_path}")

    if was_running:
        _graceful_glazewm_exit(cli_path)

    # If graceful shutdown was unavailable/unsuccessful, enforce the stop.
    if _process_running("glazewm.exe"):
        if not _ensure_process_stopped("glazewm.exe", "GlazeWM"):
            raise RuntimeError(
                "GlazeWM is still running. Zebar was NOT modified. "
                "Approve the administrator/UAC request, or close GlazeWM manually, "
                "then run the updater again."
            )
    else:
        print("GlazeWM is confirmed stopped.")

    # wm-exit may already have run the user's shutdown command for Zebar, but
    # verify it explicitly because CSS must not be edited while Zebar is alive.
    if not _ensure_process_stopped("zebar.exe", "Zebar"):
        raise RuntimeError(
            "Zebar is still running. Its stylesheet was NOT modified. "
            "Approve the administrator/UAC request, or close Zebar manually, "
            "then run the updater again."
        )

    if _process_running("glazewm.exe") or _process_running("zebar.exe"):
        raise RuntimeError(
            "GlazeWM/Zebar shutdown verification failed. No Zebar theme change was made."
        )

    print("GlazeWM and Zebar are both confirmed stopped. Theme update may continue.")
    return {"cli": cli_path, "main": main_path, "was_running": was_running}


def relaunch_glazewm(session=None):
    """Start GlazeWM once; GlazeWM's startup config is responsible for Zebar."""
    if os.name != "nt":
        print("Skipping GlazeWM relaunch outside Windows.")
        return

    session = session or {}
    cli_path = session.get("cli") or find_glazewm_cli()
    main_path = session.get("main") or find_glazewm_main()

    # Never knowingly create a duplicate instance.
    if _process_running("glazewm.exe"):
        print("GlazeWM is already running; skipping relaunch to avoid a duplicate instance.")
        return

    print("Starting GlazeWM...")

    # The supported CLI syntax is `glazewm.exe start`. Prefer it when possible.
    if cli_path and Path(cli_path).exists():
        result = _run_quiet([str(cli_path), "start"], timeout=15)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown start error").strip()
            print(f"GlazeWM CLI start failed: {detail}")
        else:
            time.sleep(0.75)
            if _process_running("glazewm.exe"):
                print("GlazeWM relaunched. Zebar is left to GlazeWM's startup config.")
                return

    # Fallback for installations where the main executable is directly launchable.
    if main_path and Path(main_path).exists():
        subprocess.Popen(
            [str(main_path), "start"],
            cwd=str(Path(main_path).parent),
            close_fds=True,
            creationflags=CREATE_NEW_PROCESS_GROUP,
        )
        time.sleep(0.75)
        if _process_running("glazewm.exe"):
            print("GlazeWM relaunched. Zebar is left to GlazeWM's startup config.")
            return

    raise FileNotFoundError(
        "The Zebar update finished, but GlazeWM could not be restarted. "
        "Set GLAZEWM_CLI_PATH to the CLI glazewm.exe or GLAZEWM_PATH to the "
        "main GlazeWM executable if your installation uses a custom location."
    )
