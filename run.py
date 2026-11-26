"""
TransactionGuard Application Launcher
Starts the FastAPI Backend & Interactive Developer Assurance Dashboard.
"""

import os
import sys
import argparse
import socket
import uvicorn

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def find_available_port(preferred_port=8080):
    for port in [preferred_port, 8080, 5000, 8001, 8888]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', port))
            s.close()
            return port
        except Exception:
            continue
    return 8080

def main():
    parser = argparse.ArgumentParser(description="TransactionGuard Launcher")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable live auto-reloading")
    args = parser.parse_args()

    port = find_available_port(args.port)

    print("=" * 75)
    print("  TransactionGuard: Concurrency Assurance & Anomaly Detection Platform")
    print(f"  Web Dashboard & REST API: http://127.0.0.1:{port}")
    print(f"  Interactive OpenAPI Specs: http://127.0.0.1:{port}/docs")
    print("  - Controlled Multi-Threaded Barrier Scheduler (E1-E6)")
    print("  - Two-Phase Bug Detector & Adya WR/RW/WW Dependency Graph Engine")
    print("  - Business Invariant Verification (Inventory, Overbooking, Skew)")
    print("  - Live Story: 'The Last Item Problem' (Vulnerable vs Mitigated)")
    print("=" * 75)

    uvicorn.run("backend.main:app", host=args.host, port=port, reload=args.reload)

if __name__ == "__main__":
    main()
