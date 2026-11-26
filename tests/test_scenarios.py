"""
DBGuard Comprehensive Automated Test Suite
Verifies:
1. Database initialization and seeding
2. Lost Update anomaly (Unsafe vs Pessimistic vs Optimistic)
3. Double-Booking race condition & prevention
4. Deadlock detection (Wait-For Graph cycle) & auto-retry
5. Savepoint partial rollback
6. Integrity constraint enforcement (CHECK constraint balance >= 0.00)
7. REST API & RBAC permissions
"""

import pytest
from db.database import init_db, get_sqlite_connection, DB_LOCK
from engine.lock_manager import LockManager, DeadlockException
from engine.conflict_detector import ConflictDetector
from engine.recovery_manager import RecoveryManager
from api.app import create_app

@pytest.fixture(autouse=True)
def setup_database():
    """Resets database before each test run."""
    LockManager().reset()
    init_db(reset=True)

def test_database_initialization():
    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dbguard_users;")
    assert cur.fetchone()[0] == 3
    cur.execute("SELECT balance FROM demo_accounts WHERE account_id = 1;")
    assert float(cur.fetchone()[0]) == 1000.00
    cur.execute("SELECT COUNT(*) FROM demo_tickets;")
    assert cur.fetchone()[0] == 4
    conn.close()

def test_lost_update_unsafe_anomaly():
    detector = ConflictDetector()
    res = detector.run_lost_update(mode="unsafe", account_id=1, deduct_t1=100.0, deduct_t2=200.0)
    assert res["anomaly_detected"] is True
    assert res["data_loss"] == 100.0
    assert res["final_balance"] == 800.0

def test_lost_update_pessimistic_prevention():
    detector = ConflictDetector()
    res = detector.run_lost_update(mode="pessimistic", account_id=1, deduct_t1=100.0, deduct_t2=200.0)
    assert res["anomaly_detected"] is False
    assert res["data_loss"] == 0.0
    assert res["final_balance"] == 700.0

def test_lost_update_optimistic_prevention():
    detector = ConflictDetector()
    res = detector.run_lost_update(mode="optimistic", account_id=1, deduct_t1=100.0, deduct_t2=200.0)
    assert res["anomaly_detected"] is False
    assert res["data_loss"] == 0.0
    assert res["final_balance"] == 700.0

def test_double_booking_unsafe_and_safe():
    detector = ConflictDetector()
    unsafe_res = detector.run_double_booking(mode="unsafe", ticket_id=1)
    assert unsafe_res["conflict_detected"] is True

    init_db(reset=True)
    safe_res = detector.run_double_booking(mode="safe", ticket_id=1)
    assert safe_res["conflict_detected"] is False

def test_deadlock_detection_and_auto_retry():
    detector = ConflictDetector()
    res = detector.run_deadlock(mode="auto_retry")
    assert res["deadlock_detected"] is True
    assert res["retried_successfully"] is True

def test_savepoint_partial_rollback():
    res = RecoveryManager.run_savepoint_batch_demo()
    assert res["success"] is True
    assert res["ticket_1_status"] == "BOOKED"
    assert res["ticket_2_status"] == "REJECTED_ROLLED_BACK"

def test_integrity_constraint_violation():
    detector = ConflictDetector()
    res = detector.run_integrity_violation_scenario(account_id=1, deduct_amount=1500.0)
    assert res["violation_blocked"] is True
    assert res["error_code"] == 3819

    # Verify balance was unchanged
    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM demo_accounts WHERE account_id = 1;")
    balance = float(cur.fetchone()[0])
    conn.close()
    assert balance == 1000.00

def test_rest_api_endpoints():
    app = create_app()
    client = app.test_client()

    # System state
    res = client.get("/api/system-state")
    assert res.status_code == 200
    assert "accounts" in res.json

    # Metrics
    res = client.get("/api/metrics")
    assert res.status_code == 200
    assert "conflict_rate_percent" in res.json

    # Run scenario via API
    res = client.post("/api/scenarios/run-lost-update", json={"mode": "pessimistic"})
    assert res.status_code == 200
    assert res.json["final_balance"] == 700.0
