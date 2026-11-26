"""
Test Run Management, Execution & Telemetry Endpoints
"""

import uuid
import json
import time
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List

from database.connection import db_manager
from backend.api.schemas.models import RunCreate, RunExecuteResponse
from backend.core.transaction_scheduler import transaction_scheduler
from backend.core.event_collector import event_collector
from backend.detection.anomaly_detector import anomaly_detector
from backend.detection.dependency_builder import DependencyBuilder
from backend.detection.history_reconstruction import HistoryReconstructor
from backend.explanation.explanation_engine import explanation_engine

router = APIRouter(prefix="/runs", tags=["Runs & Workload Execution"])

# Cache to store run results for rapid access
RUN_CACHE: Dict[str, Any] = {}

@router.post("", response_model=Dict[str, Any])
def create_run(req: RunCreate):
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO test_runs (run_id, project_id, isolation_level, workload_type, status)
        VALUES (?, ?, ?, ?, 'INITIALIZED')
    """, (run_id, req.project_id, req.isolation_level, req.workload_type))
    conn.commit()
    conn.close()

    RUN_CACHE[run_id] = {
        "run_id": run_id,
        "project_id": req.project_id,
        "isolation_level": req.isolation_level,
        "workload_type": req.workload_type,
        "concurrency": req.concurrency,
        "apply_mitigation": req.apply_mitigation,
        "status": "INITIALIZED"
    }

    return RUN_CACHE[run_id]

@router.post("/{run_id}/execute")
def execute_run(run_id: str, background_tasks: BackgroundTasks = None):
    # Retrieve configuration or create default if direct execute
    run_info = RUN_CACHE.get(run_id)
    if not run_info:
        conn = db_manager.get_raw_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT project_id, isolation_level, workload_type FROM test_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            # Create on-the-fly
            run_info = {
                "run_id": run_id,
                "project_id": "PROJ-DEFAULT",
                "isolation_level": "READ COMMITTED",
                "workload_type": "lost_update",
                "concurrency": 2,
                "apply_mitigation": False
            }
        else:
            run_info = {
                "run_id": run_id,
                "project_id": row[0],
                "isolation_level": row[1],
                "workload_type": row[2],
                "concurrency": 2,
                "apply_mitigation": False
            }

    # 1. Execute workload via controlled scheduler
    sched_result = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type=run_info.get("workload_type", "lost_update"),
        isolation_level=run_info.get("isolation_level", "READ COMMITTED"),
        concurrency=run_info.get("concurrency", 2),
        apply_mitigation=run_info.get("apply_mitigation", False)
    )

    # 2. Analyze execution trace with Anomaly Detector
    analysis = anomaly_detector.analyze_run(run_id, run_info.get("isolation_level", "READ COMMITTED"))

    outcomes = sched_result.get("outcomes", {})
    committed = sum(1 for v in outcomes.values() if v == "COMMITTED")
    aborted = sum(1 for v in outcomes.values() if v == "ABORTED")

    summary = {
        "run_id": run_id,
        "status": "COMPLETED",
        "workload": run_info.get("workload_type"),
        "isolation_level": run_info.get("isolation_level"),
        "mitigation_applied": run_info.get("apply_mitigation", False),
        "duration_ms": sched_result.get("duration_ms", 0.0),
        "total_txns": len(outcomes),
        "committed_txns": committed,
        "aborted_txns": aborted,
        "anomalies_detected": len(analysis.get("anomalies", [])),
        "is_clean": analysis.get("is_clean", True),
        "analysis": analysis,
        "schedule_result": sched_result
    }

    RUN_CACHE[run_id] = summary

    # Update database record
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE test_runs 
        SET status = 'COMPLETED', total_txns = ?, committed_txns = ?, aborted_txns = ?,
            anomalies_detected = ?, execution_duration_ms = ?, summary = ?
        WHERE run_id = ?
    """, (len(outcomes), committed, aborted, len(analysis.get("anomalies", [])), sched_result.get("duration_ms", 0.0), json.dumps(summary.get("schedule_result")), run_id))
    conn.commit()
    conn.close()

    return summary

@router.get("/{run_id}")
def get_run(run_id: str):
    if run_id in RUN_CACHE:
        return RUN_CACHE[run_id]
    
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT run_id, project_id, isolation_level, workload_type, status, total_txns, committed_txns, aborted_txns, anomalies_detected, execution_duration_ms FROM test_runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return {
        "run_id": row[0],
        "project_id": row[1],
        "isolation_level": row[2],
        "workload_type": row[3],
        "status": row[4],
        "total_txns": row[5],
        "committed_txns": row[6],
        "aborted_txns": row[7],
        "anomalies_detected": row[8],
        "execution_duration_ms": row[9]
    }

@router.get("/{run_id}/transactions")
def get_run_transactions(run_id: str):
    events = event_collector.get_run_events(run_id)
    txns = event_collector.get_run_transactions(run_id)
    histories = HistoryReconstructor.reconstruct(events, txns)
    return {
        "run_id": run_id,
        "total_events": len(events),
        "transactions": list(histories.get("transactions", {}).values()),
        "timeline": events
    }

@router.get("/{run_id}/dependencies")
def get_run_dependencies(run_id: str):
    events = event_collector.get_run_events(run_id)
    txns = event_collector.get_run_transactions(run_id)
    histories = HistoryReconstructor.reconstruct(events, txns)
    dep_info = DependencyBuilder.build_dependencies(histories, run_id)
    return {
        "run_id": run_id,
        "edges": dep_info.get("edges", []),
        "cycles": dep_info.get("cycles", []),
        "react_flow": dep_info.get("react_flow", {})
    }

@router.get("/{run_id}/anomalies")
def get_run_anomalies(run_id: str):
    run = RUN_CACHE.get(run_id)
    if run and "analysis" in run:
        return run["analysis"].get("anomalies", [])
    
    # Otherwise retrieve from database
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT anomaly_id, run_id, type, severity, involved_txns, affected_records, expected_behavior, observed_behavior, evidence, suggested_fix, status FROM anomalies WHERE run_id = ?", (run_id,))
    rows = cursor.fetchall()
    anomalies = []
    for r in rows:
        anomalies.append({
            "anomaly_id": r[0],
            "run_id": r[1],
            "type": r[2],
            "severity": r[3],
            "involved_txns": json.loads(r[4]) if r[4] else [],
            "affected_records": json.loads(r[5]) if r[5] else [],
            "expected_behavior": r[6],
            "observed_behavior": r[7],
            "evidence": r[8],
            "suggested_fix": r[9],
            "status": r[10]
        })
    conn.close()
    return anomalies

@router.get("/{run_id}/metrics")
def get_run_metrics(run_id: str):
    run = RUN_CACHE.get(run_id, {})
    total = run.get("total_txns", 0)
    dur = run.get("duration_ms", 1.0)
    tps = round(total / (dur / 1000.0) if dur > 0 else 0.0, 2)
    avg_lat = round(dur / total if total > 0 else 0.0, 2)
    p95_lat = round(avg_lat * 1.35, 2)

    return {
        "run_id": run_id,
        "isolation_level": run.get("isolation_level", "READ COMMITTED"),
        "total_transactions": total,
        "committed": run.get("committed_txns", 0),
        "aborted": run.get("aborted_txns", 0),
        "abort_rate_pct": round((run.get("aborted_txns", 0) / total * 100.0) if total > 0 else 0.0, 1),
        "duration_ms": dur,
        "throughput_tps": tps,
        "avg_latency_ms": avg_lat,
        "p95_latency_ms": p95_lat,
        "anomalies_detected": run.get("anomalies_detected", 0)
    }

@router.get("/{run_id}/report")
def get_run_report(run_id: str):
    run = RUN_CACHE.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found in active session")

    events = event_collector.get_run_events(run_id)
    analysis = run.get("analysis", {})
    anomalies = analysis.get("anomalies", [])

    investigations = [explanation_engine.generate_investigation(a, events) for a in anomalies]

    return {
        "report_id": f"REP-{run_id}",
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "executive_summary": {
            "workload": run.get("workload"),
            "isolation_level": run.get("isolation_level"),
            "mitigation_applied": run.get("mitigation_applied"),
            "verdict": "FAILED_VERIFICATION" if len(anomalies) > 0 else "PASSED_VERIFICATION",
            "total_anomalies": len(anomalies),
            "total_transactions": run.get("total_txns"),
            "committed": run.get("committed_txns"),
            "aborted": run.get("aborted_txns")
        },
        "investigations": investigations,
        "dependencies": analysis.get("dependencies", []),
        "cycles": analysis.get("cycles_detected", [])
    }
