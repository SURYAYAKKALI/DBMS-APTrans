"""
DBGuard Transaction Manager
Tracks transaction lifecycle, isolation levels, execution traces,
and savepoints with microsecond precision.
"""

import time
import json
import uuid
import datetime
from db.database import get_sqlite_connection, DB_LOCK
from engine.lock_manager import LockManager

class Transaction:
    def __init__(self, tx_id, session_id, user_id, scenario_name, isolation_level="REPEATABLE_READ"):
        self.tx_id = tx_id
        self.session_id = session_id
        self.user_id = user_id
        self.scenario_name = scenario_name
        self.isolation_level = isolation_level
        self.status = "ACTIVE"
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.affected_rows = 0
        self.savepoints = {}  # name -> snapshot of state or rollback point
        self.execution_trace = []  # Detailed step-by-step trace for UI playback

    def record_step(self, thread_name, action, resource, value=None, status="SUCCESS", wait_ms=0.0):
        step = {
            "step_no": len(self.execution_trace) + 1,
            "timestamp": datetime.datetime.now().isoformat(),
            "tx_id": self.tx_id,
            "thread": thread_name,
            "action": action,
            "resource": resource,
            "value": value,
            "wait_ms": wait_ms,
            "status": status
        }
        self.execution_trace.append(step)
        return step

class TransactionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TransactionManager, cls).__new__(cls)
            cls._instance.active_transactions = {}
            cls._instance.lock_mgr = LockManager()
        return cls._instance

    def begin(self, user_id=None, scenario_name="Custom Transaction", isolation_level="REPEATABLE READ", thread_tag="T1"):
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        session_id = f"sess_{thread_tag}_{uuid.uuid4().hex[:6]}"
        tx = Transaction(tx_id, session_id, user_id, scenario_name, isolation_level)
        self.active_transactions[tx_id] = tx

        # Persist to transaction_logs table
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO transaction_logs (transaction_id, user_id, session_id, scenario_name, isolation_level, status, affected_rows, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (tx_id, user_id, session_id, scenario_name, isolation_level, "RUNNING", 0, json.dumps({"started_by": thread_tag})))
            conn.commit()
            conn.close()

        tx.record_step(thread_tag, "START TRANSACTION", scenario_name, None, "SUCCESS")
        return tx

    def commit(self, tx_id, thread_tag="T1", affected_rows=1):
        if tx_id not in self.active_transactions:
            return None
        tx = self.active_transactions[tx_id]
        tx.status = "COMMITTED"
        tx.end_time = datetime.datetime.now()
        tx.affected_rows = affected_rows
        tx.record_step(thread_tag, "COMMIT", tx.scenario_name, f"rows={affected_rows}", "COMMITTED")

        # Release any locks held
        self.lock_mgr.release_locks_for_tx(tx_id)

        # Update log
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE transaction_logs
                SET status = 'COMMITTED', end_time = CURRENT_TIMESTAMP, affected_rows = ?, details = ?
                WHERE transaction_id = ?;
            """, (affected_rows, json.dumps({"steps": len(tx.execution_trace)}), tx_id))
            conn.commit()
            conn.close()

        del self.active_transactions[tx_id]
        return tx

    def rollback(self, tx_id, thread_tag="T1", reason="Manual Rollback", deadlock=False):
        if tx_id not in self.active_transactions:
            return None
        tx = self.active_transactions[tx_id]
        tx.status = "DEADLOCK_ABORTED" if deadlock else "ROLLED_BACK"
        tx.end_time = datetime.datetime.now()
        tx.record_step(thread_tag, "ROLLBACK", tx.scenario_name, reason, tx.status)

        # Release locks
        self.lock_mgr.release_locks_for_tx(tx_id)

        # Update log
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE transaction_logs
                SET status = ?, end_time = CURRENT_TIMESTAMP, details = ?
                WHERE transaction_id = ?;
            """, (tx.status, json.dumps({"reason": reason, "deadlock": deadlock}), tx_id))
            conn.commit()
            conn.close()

        del self.active_transactions[tx_id]
        return tx

    def savepoint(self, tx_id, savepoint_name, snapshot_data=None, thread_tag="T1"):
        if tx_id not in self.active_transactions:
            return None
        tx = self.active_transactions[tx_id]
        tx.savepoints[savepoint_name] = snapshot_data
        tx.record_step(thread_tag, f"SAVEPOINT {savepoint_name}", "SAVEPOINT", None, "SUCCESS")
        return tx

    def rollback_to_savepoint(self, tx_id, savepoint_name, thread_tag="T1"):
        if tx_id not in self.active_transactions:
            return None
        tx = self.active_transactions[tx_id]
        if savepoint_name in tx.savepoints:
            snapshot = tx.savepoints[savepoint_name]
            tx.record_step(thread_tag, f"ROLLBACK TO SAVEPOINT {savepoint_name}", "PARTIAL_ROLLBACK", None, "SUCCESS")
            return snapshot
        return None
