"""
TransactionGuard Instrumentation Engine
Transparently intercepts read/write operations and records transactional telemetry.
"""

import time
import sqlite3
from typing import Optional, Any, Dict, List
from backend.core.event_collector import event_collector

class InstrumentedSession:
    def __init__(self, raw_conn, run_id: str, txn_id: str, session_id: str, isolation_level: str = "READ COMMITTED"):
        self.conn = raw_conn
        self.run_id = run_id
        self.txn_id = txn_id
        self.session_id = session_id
        self.isolation_level = isolation_level
        self.active = True
        self.read_set: List[Dict[str, Any]] = []
        self.write_set: List[Dict[str, Any]] = []
        self.start_time = time.time()

        event_collector.start_transaction(run_id, txn_id, session_id, isolation_level)
        event_collector.record_operation(
            run_id=self.run_id,
            txn_id=self.txn_id,
            session_id=self.session_id,
            operation_type="BEGIN",
            table_name="SYSTEM",
            row_id="0",
            status="COMMITTED"
        )

    def record_read(self, table_name: str, row_id: str, value: Any, version: Optional[int] = None):
        self.read_set.append({"table": table_name, "row_id": str(row_id), "value": value, "version": version})
        return event_collector.record_operation(
            run_id=self.run_id,
            txn_id=self.txn_id,
            session_id=self.session_id,
            operation_type="READ",
            table_name=table_name,
            row_id=str(row_id),
            old_value=value,
            version=version,
            status="SUCCESS"
        )

    def record_write(self, table_name: str, row_id: str, old_value: Any, new_value: Any, version: Optional[int] = None):
        self.write_set.append({"table": table_name, "row_id": str(row_id), "old_value": old_value, "new_value": new_value, "version": version})
        return event_collector.record_operation(
            run_id=self.run_id,
            txn_id=self.txn_id,
            session_id=self.session_id,
            operation_type="WRITE",
            table_name=table_name,
            row_id=str(row_id),
            old_value=old_value,
            new_value=new_value,
            version=version,
            status="SUCCESS"
        )

    def commit(self):
        try:
            self.conn.commit()
            event_collector.record_operation(
                run_id=self.run_id,
                txn_id=self.txn_id,
                session_id=self.session_id,
                operation_type="COMMIT",
                table_name="SYSTEM",
                row_id="0",
                status="COMMITTED"
            )
            event_collector.end_transaction(self.txn_id, outcome="COMMITTED")
            self.active = False
        except Exception as e:
            self.rollback(str(e))
            raise

    def rollback(self, reason: Optional[str] = None):
        try:
            self.conn.rollback()
        except Exception:
            pass
        finally:
            event_collector.record_operation(
                run_id=self.run_id,
                txn_id=self.txn_id,
                session_id=self.session_id,
                operation_type="ROLLBACK",
                table_name="SYSTEM",
                row_id="0",
                old_value=reason,
                status="ABORTED"
            )
            event_collector.end_transaction(self.txn_id, outcome="ABORTED", error_message=reason)
            self.active = False

    def close(self):
        try:
            if self.active:
                self.rollback("Session closed before commit")
            self.conn.close()
        except Exception:
            pass
