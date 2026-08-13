from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

# Support `python src/commodity_engine/main.py` as well as the installed console command.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing runtime dependencies. From the project folder run:\n"
            "  py -3.12 -m venv .venv\n"
            "  .\\.venv\\Scripts\\python.exe -m pip install -e .\n"
            "Then start with:\n"
            "  .\\.venv\\Scripts\\python.exe src\\commodity_engine\\main.py"
        ) from exc
    host = "127.0.0.1"
    port = int(os.getenv("ENGINE_PORT", "8000"))
    url = f"http://{host}:{port}/full-report"
    with socket.socket() as probe:
        if probe.connect_ex((host, port)) == 0:
            raise SystemExit(
                f"Port {port} is already in use, probably by an older engine.\n"
                "Stop the older terminal with Ctrl+C, then run this file again.\n"
                f"If it is already the current engine, open: {url}"
            )
    print("\n" + "=" * 72)
    print(" COMMODITY PRICING ENGINE IS STARTING")
    print(f" Complete simulation and report: {url}")
    print(f" Pricing dashboard:              http://{host}:{port}/")
    print(f" Time and accuracy report:       http://{host}:{port}/report/comparison")
    print(" Keep this terminal open. Press Ctrl+C to stop the server.")
    print("=" * 72 + "\n")
    if os.getenv("ENGINE_OPEN_BROWSER", "1") == "1":
        threading.Timer(1.25, lambda: webbrowser.open(url)).start()
    uvicorn.run("commodity_engine.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
