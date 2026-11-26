"""
Anomaly Investigation Endpoints
"""

import json
from fastapi import APIRouter, HTTPException
from database.connection import db_manager
from backend.explanation.explanation_engine import explanation_engine
from backend.core.event_collector import event_collector

router = APIRouter(prefix="/anomalies", tags=["Anomalies & Investigation"])

@router.get("/{anomaly_id}")
def get_anomaly_detail(anomaly_id: str):
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT anomaly_id, run_id, type, severity, involved_txns, affected_records, 
               expected_behavior, observed_behavior, evidence, suggested_fix, status
        FROM anomalies WHERE anomaly_id = ?
    """, (anomaly_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly_obj = {
        "anomaly_id": row[0],
        "run_id": row[1],
        "type": row[2],
        "severity": row[3],
        "involved_txns": json.loads(row[4]) if row[4] else [],
        "affected_records": json.loads(row[5]) if row[5] else [],
        "expected_behavior": row[6],
        "observed_behavior": row[7],
        "evidence": row[8],
        "suggested_fix": row[9],
        "status": row[10]
    }

    events = event_collector.get_run_events(anomaly_obj["run_id"])
    investigation = explanation_engine.generate_investigation(anomaly_obj, events)
    return investigation
