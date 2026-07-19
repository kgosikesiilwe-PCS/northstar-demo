#!/usr/bin/env python3
"""One-command local launcher for NorthStar MVP.

Run with: python START_HERE.py
It creates a virtual environment, installs requirements, initializes the database,
opens your browser, and starts the local app.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
MARKER = VENV_DIR / ".northstar_deps_installed"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(cmd: list[str], *, check: bool = True) -> int:
    print("\n> " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT)
    if check and result.returncode != 0:
        print("\nThat command failed. Copy the lines above and send them to the developer/ChatGPT.")
        sys.exit(result.returncode)
    return result.returncode


def ensure_python_version() -> None:
    if sys.version_info < (3, 10):
        print("NorthStar needs Python 3.10 or newer.")
        print("Install the latest Python from python.org, then run this file again.")
        sys.exit(1)


def ensure_venv() -> None:
    if not venv_python().exists():
        print("Creating local Python environment in .venv ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)


def install_requirements() -> None:
    py = str(venv_python())
    req = ROOT / "requirements.txt"
    if not req.exists():
        print("Missing requirements.txt. Make sure you are running this inside the northstar_mvp folder.")
        sys.exit(1)
    # Install each time if requirements changed; otherwise use marker for faster startup.
    req_fingerprint = req.read_text(encoding="utf-8")
    marker_text = MARKER.read_text(encoding="utf-8") if MARKER.exists() else ""
    if marker_text == req_fingerprint:
        print("Dependencies already installed.", flush=True)
        return
    print("Installing app dependencies. This may take a few minutes the first time ...", flush=True)
    run([py, "-m", "pip", "install", "--upgrade", "pip"])
    run([py, "-m", "pip", "install", "-r", "requirements.txt"])
    MARKER.write_text(req_fingerprint, encoding="utf-8")


def pick_port(start: int = 8000, end: int = 8010) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    print("Ports 8000-8010 are already in use. Close other local servers and try again.")
    sys.exit(1)


def main() -> None:
    ensure_python_version()
    os.chdir(ROOT)
    ensure_venv()
    install_requirements()
    py = str(venv_python())
    print("\nInitializing local database ...", flush=True)
    run([py, "-m", "app.main", "init-db"])
    port = pick_port()
    url = f"http://127.0.0.1:{port}"
    print("\nNorthStar is starting.")
    print(f"Opening: {url}")
    print("Leave this window open while testing. Press Ctrl+C to stop the app.\n")
    time.sleep(1)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        run([py, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], check=False)
    except KeyboardInterrupt:
        print("\nNorthStar stopped.")


if __name__ == "__main__":
    main()
