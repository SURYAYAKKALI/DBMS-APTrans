"""
Unit Test: Dirty Read Anomaly Detection
"""

import pytest
from database.connection import db_manager
from backend.core.transaction_scheduler import transaction_scheduler
from backend.detection.anomaly_detector import anomaly_detector

def test_dirty_read_prevention():
    db_manager.init_database()
    run_id = "TEST-DR-RUN"

    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="dirty_read",
        isolation_level="READ COMMITTED"
    )

    # In Read Committed, reader should NOT observe uncommitted 99
    assert res["outcomes"]["TXN-DR-WRITER"] == "ABORTED"
    assert res["outcomes"]["TXN-DR-READER"] == "COMMITTED"
    assert res["observed_value"][0] == 3
