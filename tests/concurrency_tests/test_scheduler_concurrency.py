"""
Concurrency Scheduler Stress and Scale Tests
"""

import pytest
from database.connection import db_manager
from backend.core.transaction_scheduler import transaction_scheduler

def test_concurrent_stress_execution():
    db_manager.init_database()
    run_id = "TEST-STRESS-10"

    res = transaction_scheduler.execute_workload(
        run_id=run_id,
        workload_type="stress_concurrency",
        isolation_level="READ COMMITTED",
        concurrency=10
    )

    outcomes = res.get("outcomes", {})
    assert len(outcomes) == 10
    assert sum(1 for v in outcomes.values() if v == "COMMITTED") > 0
    assert res["duration_ms"] > 0
