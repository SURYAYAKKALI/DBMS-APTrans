"""
TransactionGuard Main Application Entrypoint
FastAPI Backend orchestrating concurrency workloads, telemetry capture,
anomaly detection, and interactive dashboard serving.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from database.connection import db_manager
from backend.api.routes import projects, runs, anomalies, rules, metrics, demo

# Initialize DB schema & seed on startup
print("[TransactionGuard] Initializing Database schema and seed data...")
try:
    db_manager.init_database()
    print("[TransactionGuard] Database initialized successfully!")
except Exception as e:
    print(f"[TransactionGuard] Warning during DB init: {e}")

app = FastAPI(
    title="TransactionGuard API",
    description="Intelligent Database Transaction Anomaly Detection & Concurrency Assurance Platform",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(projects.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(anomalies.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(demo.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "TransactionGuard",
        "database_engine": "postgresql" if db_manager.is_postgres else "sqlite_wal",
        "version": "2.0.0"
    }

# Mount static folder for dashboard assets
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>TransactionGuard API is running. Visit <a href='/docs'>/docs</a>.</h2>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
