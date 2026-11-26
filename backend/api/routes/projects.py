"""
Project & Connection Routes
"""

import time
import uuid
from fastapi import APIRouter, HTTPException
from typing import List
from database.connection import db_manager, DatabaseManager
from backend.api.schemas.models import ProjectCreate, ProjectResponse, ConnectionTestRequest, ConnectionTestResponse

router = APIRouter(tags=["Projects & Connections"])

@router.post("/projects", response_model=ProjectResponse)
def create_project(req: ProjectCreate):
    pid = f"PROJ-{uuid.uuid4().hex[:8].upper()}"
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO test_projects (project_id, name, description, database_config) VALUES (?, ?, ?, ?)",
        (pid, req.name, req.description, req.database_config)
    )
    conn.commit()
    conn.close()
    return {
        "project_id": pid,
        "name": req.name,
        "description": req.description,
        "database_config": req.database_config,
        "created_at": None
    }

@router.get("/projects", response_model=List[ProjectResponse])
def list_projects():
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT project_id, name, description, database_config, created_at FROM test_projects")
    rows = cursor.fetchall()
    projects = []
    for r in rows:
        projects.append({
            "project_id": r[0],
            "name": r[1],
            "description": r[2],
            "database_config": r[3],
            "created_at": str(r[4]) if r[4] else None
        })
    conn.close()
    return projects

@router.post("/connections/test", response_model=ConnectionTestResponse)
def test_connection(req: ConnectionTestRequest):
    t0 = time.time()
    try:
        url = req.database_url or db_manager.db_url
        mgr = DatabaseManager.get_instance(url)
        conn = mgr.get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        elapsed = (time.time() - t0) * 1000.0
        engine_name = "postgresql" if mgr.is_postgres else ("mysql" if mgr.is_mysql else "sqlite")
        return {
            "success": True,
            "engine": engine_name,
            "message": f"Successfully connected to {engine_name.upper()} database instance.",
            "latency_ms": round(elapsed, 2)
        }
    except Exception as e:
        elapsed = (time.time() - t0) * 1000.0
        return {
            "success": False,
            "engine": req.engine_type,
            "message": f"Connection failed: {str(e)}",
            "latency_ms": round(elapsed, 2)
        }

@router.post("/connections/switch")
def switch_database_connection(req: ConnectionTestRequest):
    if not req.database_url:
        raise HTTPException(status_code=400, detail="database_url is required")
    try:
        new_mgr = DatabaseManager.switch_database(req.database_url)
        engine_name = "postgresql" if new_mgr.is_postgres else ("mysql" if new_mgr.is_mysql else "sqlite")
        return {
            "success": True,
            "engine": engine_name,
            "active_database_url": req.database_url,
            "message": f"Active database successfully switched to {engine_name.upper()} and initialized!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to switch database: {str(e)}")
