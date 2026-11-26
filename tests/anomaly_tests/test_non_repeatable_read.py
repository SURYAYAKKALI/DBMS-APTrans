"""
Unit Test: Non-Repeatable Read Verification
"""

import pytest
from database.connection import db_manager
from backend.core.transaction_scheduler import transaction_scheduler
from backend.detection.anomaly_detector import anomaly_detector

def test_non_repeatable_read_detected():
    db_manager.init_database()
    run_id = "TEST-NRR-RUN"

    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="non_repeatable_read",
        isolation_level="READ COMMITTED"
    )

    assert res["outcomes"]["TXN-NRR-READER"] == "COMMITTED"
    assert res["outcomes"]["TXN-NRR-WRITER"] == "COMMITTED"
    assert res["observed_reads"][0] != res["observed_reads"][1]

    analysis = anomaly_detector.analyze_run(run_id, "READ COMMITTED")
    types = [a["type"] for a in analysis["anomalies"]]
    assert "NON_REPEATABLE_READ" in types
