"""
APTrans & DBGuard Unified Platform Launcher
ACM SIGMOD 2026 Paper Reconstruction & Interactive Live Concurrency Studio
"""

import os
import sys
import argparse
import socket
import threading
import time
import webbrowser

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def find_available_port(preferred_port=5000):
    for port in [preferred_port, 5000, 5001, 8080, 8000, 8888]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', port))
            s.close()
            return port
        except Exception:
            continue
    return preferred_port

def open_browser_delayed(url, delay=1.2):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Thread(target=_open, daemon=True).start()

def run_aptrans_flask(host="127.0.0.1", port=5000, debug=False, open_browser=True):
    from api.app import create_app
    app = create_app()

    url = f"http://{host}:{port}"
    print("=" * 76)
    print("  APTrans: Anomaly Pattern-guided Transaction Bug Testing Platform")
    print("  ACM SIGMOD 2026 Paper Reconstruction & Interactive Concurrency Studio")
    print("=" * 76)
    print(f"  --> Interactive Web Dashboard: {url}")
    print(f"  --> Live Studio (Break It vs Fix It): {url}#livesim")
    print(f"  --> 46 Anomaly Patterns Catalog:    {url}#patterns")
    print(f"  --> Real-World Case Studies:        {url}#casestudies")
    print(f"  --> Professor Evaluation Rubric:    {url}#evaluation")
    print("=" * 76)
    print("  Press Ctrl+C to stop the server.\n")

    if open_browser:
        open_browser_delayed(url)

    # Use 0.0.0.0 to allow access from local machine and LAN
    bind_host = "0.0.0.0" if host in ["127.0.0.1", "localhost"] else host
    app.run(host=bind_host, port=port, debug=debug, use_reloader=False)

def run_fastapi_backend(host="127.0.0.1", port=8080, reload=False, open_browser=True):
    import uvicorn
    url = f"http://{host}:{port}"
    print("=" * 76)
    print("  TransactionGuard FastAPI Platform")
    print(f"  --> API & Docs: {url}/docs")
    print("=" * 76)

    if open_browser:
        open_browser_delayed(f"{url}/docs")

    bind_host = "0.0.0.0" if host in ["127.0.0.1", "localhost"] else host
    uvicorn.run("backend.main:app", host=bind_host, port=port, reload=reload)

def main():
    parser = argparse.ArgumentParser(description="APTrans & DBGuard Platform Launcher")
    parser.add_argument("--mode", "--app", choices=["aptrans", "flask", "fastapi", "transactionguard"],
                        default="aptrans", help="Application engine to launch (default: aptrans)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind to (default: 5000 for aptrans, 8080 for fastapi)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the browser")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Determine default port based on application mode
    if args.port is None:
        target_port = 8080 if args.mode in ["fastapi", "transactionguard"] else 5000
    else:
        target_port = args.port

    actual_port = find_available_port(target_port)

    should_open = not args.no_browser

    if args.mode in ["fastapi", "transactionguard"]:
        run_fastapi_backend(host=args.host, port=actual_port, reload=args.debug, open_browser=should_open)
    else:
        run_aptrans_flask(host=args.host, port=actual_port, debug=args.debug, open_browser=should_open)

if __name__ == "__main__":
    main()
