"""Simple New Tab extension color synchronization for Vivaldi."""

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from color_picker import PALETTE
from common import backup_directory_zip, backup_json_value
from vivaldi import VIVALDI_EXE, VIVALDI_PREFERENCES, is_vivaldi_running

SIMPLE_NEW_TAB_EXTENSION_ID = "knjgndjhindbbphlfnaagilhcjciehaf"
SIMPLE_NEW_TAB_URL = f"chrome-extension://{SIMPLE_NEW_TAB_EXTENSION_ID}/index.html"
SIMPLE_NEW_TAB_COLOR_KEY = "simple-new-tab:colors"

def _http_json(url, method="GET", timeout=2):
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def _recv_exact(sock, count):
    chunks = []
    remaining = count

    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("WebSocket connection closed unexpectedly.")
        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)

def _ws_connect(websocket_url, timeout=5):
    """Open a minimal RFC 6455 WebSocket connection using stdlib only."""

    parsed = urllib.parse.urlparse(websocket_url)
    if parsed.scheme != "ws":
        raise ValueError(f"Unsupported DevTools WebSocket URL: {websocket_url}")

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)

    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(request.encode("ascii"))

    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)
        if len(response) > 65536:
            raise ConnectionError("Invalid WebSocket handshake response.")

    header = response.split(b"\r\n\r\n", 1)[0].decode("latin1")
    if " 101 " not in header.split("\r\n", 1)[0]:
        sock.close()
        raise ConnectionError(f"DevTools WebSocket handshake failed:\n{header}")

    expected = base64.b64encode(
        hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
        ).digest()
    ).decode("ascii")

    accept = None
    for line in header.split("\r\n")[1:]:
        if line.lower().startswith("sec-websocket-accept:"):
            accept = line.split(":", 1)[1].strip()
            break

    if accept != expected:
        sock.close()
        raise ConnectionError("DevTools WebSocket handshake validation failed.")

    return sock

def _ws_send_frame(sock, payload, opcode=0x1):
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    # Client-to-server WebSocket frames must be masked.
    first = 0x80 | opcode
    length = len(payload)

    if length < 126:
        header = bytes([first, 0x80 | length])
    elif length <= 0xFFFF:
        header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
    else:
        header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)

    mask = os.urandom(4)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    sock.sendall(header + mask + masked)

def _ws_recv_frame(sock):
    first, second = _recv_exact(sock, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F

    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]

    mask = _recv_exact(sock, 4) if masked else None
    payload = _recv_exact(sock, length) if length else b""

    if mask:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))

    return opcode, payload

def cdp_call(websocket_url, method, params=None, command_id=1, timeout=7):
    """Send one Chrome DevTools Protocol command and return its response."""

    sock = _ws_connect(websocket_url, timeout=timeout)

    try:
        message = {
            "id": command_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        _ws_send_frame(sock, json.dumps(message, separators=(",", ":")))

        while True:
            opcode, payload = _ws_recv_frame(sock)

            if opcode == 0x8:  # close
                raise ConnectionError("DevTools WebSocket closed before replying.")

            if opcode == 0x9:  # ping
                _ws_send_frame(sock, payload, opcode=0xA)
                continue

            if opcode != 0x1:
                continue

            response = json.loads(payload.decode("utf-8"))
            if response.get("id") == command_id:
                if "error" in response:
                    raise RuntimeError(
                        f"DevTools command {method} failed: {response['error']}"
                    )
                return response
    finally:
        try:
            _ws_send_frame(sock, b"", opcode=0x8)
        except Exception:
            pass
        sock.close()

def _wait_for_devtools(port, timeout=12):
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    last_error = None

    while time.time() < deadline:
        try:
            return _http_json(url, timeout=1)
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    raise RuntimeError(
        f"Vivaldi DevTools did not become available on port {port}: {last_error}"
    )

def _wait_for_vivaldi_exit(timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_vivaldi_running():
            return True
        time.sleep(0.2)
    return not is_vivaldi_running()

def _find_simple_new_tab_install_dir():
    """Return the newest installed Simple New Tab extension directory."""

    install_root = (
        VIVALDI_PREFERENCES.parent
        / "Extensions"
        / SIMPLE_NEW_TAB_EXTENSION_ID
    )

    if not install_root.exists():
        raise FileNotFoundError(
            "Simple New Tab extension directory was not found:\n"
            f"  {install_root}"
        )

    versions = [path for path in install_root.iterdir() if path.is_dir()]
    if not versions:
        raise FileNotFoundError(
            "No installed Simple New Tab version was found under:\n"
            f"  {install_root}"
        )

    return max(versions, key=lambda path: path.stat().st_mtime)

def update_simple_new_tab():
    """
    Synchronize Simple New Tab colors with PALETTE.

    Simple New Tab stores its colors in DOM localStorage under
    `simple-new-tab:colors`. Chromium stores DOM localStorage in a
    per-profile LevelDB database. Instead of editing that database by
    hand, this function copies it to a temporary Vivaldi profile,
    lets the extension itself write the new value, closes the temporary
    browser, then copies the safely-flushed database back while the real
    Vivaldi profile is closed.

    A temporary/non-default profile is also important on modern Chromium,
    where remote-debugging switches are intentionally restricted for the
    normal/default browser profile.
    """

    if not VIVALDI_EXE.exists():
        raise FileNotFoundError(
            f"Vivaldi executable not found:\n  {VIVALDI_EXE}"
        )

    extension_dir = _find_simple_new_tab_install_dir()
    real_profile = VIVALDI_PREFERENCES.parent
    real_leveldb = real_profile / "Local Storage" / "leveldb"

    if not real_leveldb.exists():
        raise FileNotFoundError(
            "Vivaldi Local Storage database was not found:\n"
            f"  {real_leveldb}"
        )

    colors = {
        "background": PALETTE["background"],
        "unfocused": PALETTE["window"],
        "accent": PALETTE["accent"],
        "body": PALETTE["foreground"],
    }

    print("Updating Simple New Tab colors...")

    with tempfile.TemporaryDirectory(prefix="theme_sync_snt_") as temp_root_str:
        temp_root = Path(temp_root_str)
        temp_profile = temp_root / "Default"
        temp_leveldb = temp_profile / "Local Storage" / "leveldb"
        temp_leveldb.parent.mkdir(parents=True, exist_ok=True)

        # Start from the real profile's current localStorage, so every
        # other website/extension localStorage value remains untouched.
        shutil.copytree(real_leveldb, temp_leveldb)

        # Reserve a currently free localhost port for the brief CDP session.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        debug_process = subprocess.Popen(
            [
                str(VIVALDI_EXE),
                f"--user-data-dir={temp_root}",
                "--start-minimized",
                "--no-first-run",
                "--no-default-browser-check",
                f"--disable-extensions-except={extension_dir}",
                f"--load-extension={extension_dir}",
                "--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={port}",
            ],
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            ),
        )

        browser_ws = None
        target_id = None
        update_succeeded = False

        try:
            version = _wait_for_devtools(port)
            browser_ws = version.get("webSocketDebuggerUrl")

            # Give the unpacked extension a moment to register in the
            # temporary profile before opening its page.
            time.sleep(0.75)

            encoded_url = urllib.parse.quote(SIMPLE_NEW_TAB_URL, safe=":/")
            last_error = None
            target = None

            for _ in range(15):
                try:
                    target = _http_json(
                        f"http://127.0.0.1:{port}/json/new?{encoded_url}",
                        method="PUT",
                        timeout=3,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.2)

            if target is None:
                raise RuntimeError(
                    "Could not open Simple New Tab in the temporary "
                    f"Vivaldi profile: {last_error}"
                )

            target_id = target["id"]
            target_ws = target["webSocketDebuggerUrl"]
            time.sleep(0.4)

            expression = f"""
(() => {{
    const key = {json.dumps(SIMPLE_NEW_TAB_COLOR_KEY)};
    const previous = localStorage.getItem(key);
    const next = {json.dumps(colors)};
    localStorage.setItem(key, JSON.stringify(next));
    return {{ previous, current: localStorage.getItem(key), origin: location.origin }};
}})()
""".strip()

            response = cdp_call(
                target_ws,
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )

            result = (
                response.get("result", {})
                .get("result", {})
                .get("value", {})
            )

            expected_origin = (
                f"chrome-extension://{SIMPLE_NEW_TAB_EXTENSION_ID}"
            )
            origin = result.get("origin")
            if origin != expected_origin:
                raise RuntimeError(
                    f"Simple New Tab opened with unexpected origin: {origin!r}"
                )

            previous_raw = result.get("previous")
            try:
                previous = json.loads(previous_raw) if previous_raw else None
            except json.JSONDecodeError:
                previous = previous_raw

            backup_json_value(
                "simple_new_tab_colors",
                {
                    "key": SIMPLE_NEW_TAB_COLOR_KEY,
                    "previous": previous,
                },
            )

            update_succeeded = True

        finally:
            # Close the temporary extension target so it is never part of
            # a real Vivaldi session.
            if target_id is not None:
                try:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/json/close/{target_id}",
                        timeout=2,
                    ).close()
                except Exception:
                    pass

            if browser_ws:
                try:
                    cdp_call(browser_ws, "Browser.close", timeout=3)
                except Exception:
                    pass

            try:
                debug_process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                debug_process.terminate()
                try:
                    debug_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    debug_process.kill()
                    debug_process.wait(timeout=3)

        if not update_succeeded:
            raise RuntimeError("Simple New Tab color update did not complete.")

        if not temp_leveldb.exists():
            raise RuntimeError(
                "Temporary Vivaldi profile did not produce a Local Storage "
                "database after the Simple New Tab update."
            )

        # Back up the complete real Local Storage DB because Chromium keeps
        # all origins together in this LevelDB directory.
        backup_directory_zip(real_leveldb, "vivaldi_local_storage")

        # Replace only after the temporary Vivaldi process has fully exited
        # and successfully flushed the localStorage write to LevelDB.
        replacement = real_leveldb.with_name("leveldb.theme_sync_new")
        if replacement.exists():
            shutil.rmtree(replacement)

        shutil.copytree(temp_leveldb, replacement)

        old = real_leveldb.with_name("leveldb.theme_sync_old")
        if old.exists():
            shutil.rmtree(old)

        real_leveldb.replace(old)
        replacement.replace(real_leveldb)
        shutil.rmtree(old)

    print("Simple New Tab colors updated:")
    for name, value in colors.items():
        print(f"  {name:<10} {value}")
