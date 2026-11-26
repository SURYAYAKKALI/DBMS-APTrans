"""
Unit Test: Write Skew (Doctor on Duty) Reproduction & Verification
Verifies that Write Skew is detected under Read Committed / Repeatable Read (Snapshot Isolation)
and prevented under Serializable isolation.
"""

import pytest
from database.connection import db_manager
from backend.core.transaction_scheduler import transaction_scheduler
from backend.detection.anomaly_detector import anomaly_detector

def test_write_skew_vulnerable():
    db_manager.init_database()
    run_id = "TEST-WS-VULN"

    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="write_skew",
        isolation_level="REPEATABLE READ",
        apply_mitigation=False
    )

    assert res["outcomes"]["TXN-DOC-01"] == "COMMITTED"
    assert res["outcomes"]["TXN-DOC-02"] == "COMMITTED"
    assert res["final_state"]["doctors_on_duty"] == 0

    analysis = anomaly_detector.analyze_run(run_id, "REPEATABLE READ")
    # Business invariant breached: at least one doctor must remain on duty
    types = [a["type"] for a in analysis["anomalies"]]
    assert any("AT-LEAST-ONE-ON-DUTY" in t or "WRITE_SKEW" in t for t in types)

def test_write_skew_mitigated():
    db_manager.init_database()
    run_id = "TEST-WS-MITIGATED"

    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="write_skew",
        isolation_level="SERIALIZABLE",
        apply_mitigation=True
    )

    # SSI prevents second doctor from leaving
    assert res["outcomes"]["TXN-DOC-01"] == "COMMITTED"
    assert res["outcomes"]["TXN-DOC-02"] == "ABORTED"
    assert res["final_state"]["doctors_on_duty"] == 1
