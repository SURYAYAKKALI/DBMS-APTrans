"""
Live Demonstration Routes: "The Last Item Problem" & "Write Skew"
Supports one-click before/after anomaly reproduction and mitigation verification.
"""

from fastapi import APIRouter
from typing import Dict, Any

from database.connection import db_manager
from business_app.inventory.service import InventoryService
from business_app.reservations.service import ReservationService
from backend.core.transaction_scheduler import transaction_scheduler
from backend.detection.anomaly_detector import anomaly_detector
from backend.explanation.explanation_engine import explanation_engine
from backend.core.event_collector import event_collector

router = APIRouter(prefix="/demo", tags=["Live Demonstration Scenarios"])

@router.get("/last-item/status")
def get_last_item_status():
    conn = db_manager.get_raw_connection()
    stock = InventoryService.get_stock(conn, "EQ-LAPTOP-01")
    conn.close()
    return {
        "equipment_id": "EQ-LAPTOP-01",
        "equipment_name": "MacBook Pro M3 Max (Dev Edition)",
        "quantity": stock["quantity"] if stock else 0,
        "version": stock["version"] if stock else 1
    }

@router.post("/last-item/reset")
def reset_last_item():
    conn = db_manager.get_raw_connection()
    InventoryService.reset_inventory(conn, "EQ-LAPTOP-01", initial_quantity=1)
    conn.close()
    return {"message": "Inventory successfully reset to initial state: Quantity = 1"}

@router.post("/last-item/run")
def run_last_item_demo(mitigation: bool = False, isolation_level: str = "READ COMMITTED"):
    """
    Executes the 'Last Item Problem' live demonstration scenario.
    - mitigation=False: Demonstrates Lost Update anomaly & overselling under READ COMMITTED
    - mitigation=True: Demonstrates Atomic / OCC / Serializable correction preserving inventory invariant
    """
    import uuid
    run_id = f"DEMO-LU-{'MITIGATED' if mitigation else 'VULNERABLE'}-{uuid.uuid4().hex[:6].upper()}"

    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="lost_update",
        isolation_level=isolation_level,
        concurrency=2,
        apply_mitigation=mitigation
    )

    analysis = anomaly_detector.analyze_run(run_id, isolation_level)
    events = event_collector.get_run_events(run_id)

    investigations = [explanation_engine.generate_investigation(a, events) for a in analysis.get("anomalies", [])]

    # Get final stock
    conn = db_manager.get_raw_connection()
    stock = InventoryService.get_stock(conn, "EQ-LAPTOP-01")
    conn.close()

    return {
        "run_id": run_id,
        "mitigation_applied": mitigation,
        "isolation_level": isolation_level,
        "final_inventory_quantity": stock["quantity"] if stock else 0,
        "schedule_result": res,
        "analysis": analysis,
        "investigations": investigations
    }

@router.post("/write-skew/run")
def run_write_skew_demo(mitigation: bool = False, isolation_level: str = "READ COMMITTED"):
    import uuid
    run_id = f"DEMO-WS-{'MITIGATED' if mitigation else 'VULNERABLE'}-{uuid.uuid4().hex[:6].upper()}"

    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="write_skew",
        isolation_level=isolation_level,
        concurrency=2,
        apply_mitigation=mitigation
    )

    analysis = anomaly_detector.analyze_run(run_id, isolation_level)
    events = event_collector.get_run_events(run_id)

    investigations = [explanation_engine.generate_investigation(a, events) for a in analysis.get("anomalies", [])]

    conn = db_manager.get_raw_connection()
    active_docs = ReservationService.get_doctors_on_duty(conn)
    conn.close()

    return {
        "run_id": run_id,
        "mitigation_applied": mitigation,
        "isolation_level": isolation_level,
        "final_doctors_on_duty": active_docs,
        "schedule_result": res,
        "analysis": analysis,
        "investigations": investigations
    }
