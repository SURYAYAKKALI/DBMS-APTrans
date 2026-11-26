"""
Unit Test: Lost Update Reproduction & Verification
Verifies that Lost Update is detected under Read Committed,
and correctly prevented when atomic/OCC mitigation or Serializable isolation is applied.
"""

import pytest
from database.connection import db_manager
from backend.core.transaction_scheduler import transaction_scheduler
from backend.detection.anomaly_detector import anomaly_detector

def test_lost_update_vulnerable():
    db_manager.init_database()
    run_id = "TEST-LU-VULN"
    
    # Run vulnerable read-modify-write without mitigation
    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="lost_update",
        isolation_level="READ COMMITTED",
        apply_mitigation=False
    )
    
    assert res["outcomes"]["TXN-01"] == "COMMITTED"
    assert res["outcomes"]["TXN-02"] == "COMMITTED"

    # Detect anomaly
    analysis = anomaly_detector.analyze_run(run_id, "READ COMMITTED")
    types = [a["type"] for a in analysis["anomalies"]]
    assert "LOST_UPDATE" in types

def test_lost_update_mitigated():
    db_manager.init_database()
    run_id = "TEST-LU-MITIGATED"

    # Run with atomic mitigation enabled
    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="lost_update",
        isolation_level="SERIALIZABLE",
        apply_mitigation=True
    )

    # Concurrency control aborts second conflicting transaction
    assert res["outcomes"]["TXN-01"] == "COMMITTED"
    assert res["outcomes"]["TXN-02"] == "ABORTED"

    analysis = anomaly_detector.analyze_run(run_id, "SERIALIZABLE")
    assert analysis["is_clean"] is True
