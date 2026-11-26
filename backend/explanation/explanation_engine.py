"""
Explainability Engine
Transforms anomaly findings into structured, evidence-backed root-cause explanations
with actionable remediation code.
"""

from typing import Dict, Any, List

class ExplanationEngine:
    @staticmethod
    def generate_investigation(anomaly: Dict[str, Any], events: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        anom_type = anomaly.get("type", "UNKNOWN")
        txns = anomaly.get("involved_txns", [])
        records = anomaly.get("affected_records", [])

        # Filter timeline events relevant to these transactions
        relevant_events = []
        if events:
            relevant_events = [e for e in events if e.get("txn_id") in txns]

        code_remediation = ""
        if anom_type == "LOST_UPDATE":
            code_remediation = """-- Solution 1: Atomic Database-Level Update
UPDATE inventory 
SET quantity = quantity - :deduct_qty 
WHERE equipment_id = :equip_id AND quantity >= :deduct_qty;

-- Solution 2: Optimistic Concurrency Control (OCC)
UPDATE inventory 
SET quantity = :new_qty, version = version + 1 
WHERE equipment_id = :equip_id AND version = :read_version;

-- Solution 3: PostgreSQL Pessimistic Row Lock
BEGIN;
SELECT quantity FROM inventory WHERE equipment_id = :equip_id FOR UPDATE;
UPDATE inventory SET quantity = quantity - :deduct_qty WHERE equipment_id = :equip_id;
COMMIT;"""

        elif anom_type == "WRITE_SKEW":
            code_remediation = """-- Solution 1: Use PostgreSQL SERIALIZABLE Isolation
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- PostgreSQL SSI engine will detect rw-antidependency cycles and abort with code 40001.

-- Solution 2: Predicate Lock via Table Locking / Materialized Conflict
BEGIN;
LOCK TABLE doctors IN SHARE UPDATE EXCLUSIVE MODE;
SELECT COUNT(*) FROM doctors WHERE shift_date = :date AND on_duty = true;
UPDATE doctors SET on_duty = false WHERE doctor_id = :id;
COMMIT;"""

        elif anom_type == "NON_REPEATABLE_READ":
            code_remediation = """-- Upgrade session isolation level to REPEATABLE READ
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT quantity FROM inventory WHERE equipment_id = :id;
-- Subsequent reads within this transaction will read from the same snapshot.
COMMIT;"""

        elif anom_type == "DIRTY_READ":
            code_remediation = """-- Modern databases prevent dirty reads by default under READ COMMITTED.
-- Ensure transaction is running with at least READ COMMITTED:
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;"""

        else:
            code_remediation = "-- Apply database integrity constraints and SERIALIZABLE isolation."

        return {
            "title": f"Root Cause Analysis: {anom_type}",
            "anomaly_type": anom_type,
            "severity": anomaly.get("severity", "HIGH"),
            "verdict": anomaly.get("verdict", "FLAGGED"),
            "compliance_note": anomaly.get("compliance_note", ""),
            "involved_transactions": txns,
            "affected_entities": records,
            "summary": f"Detected {anom_type} across {len(txns)} concurrent transaction(s).",
            "evidence": anomaly.get("evidence"),
            "expected_behavior": anomaly.get("expected_behavior"),
            "observed_behavior": anomaly.get("observed_behavior"),
            "timeline_steps": relevant_events,
            "remediation_guide": {
                "recommendation": anomaly.get("suggested_fix"),
                "sql_code": code_remediation
            }
        }

explanation_engine = ExplanationEngine()
