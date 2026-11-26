"""
TransactionGuard Application-Side Telemetry & Event Collector
Preserves independent transaction execution logs even across ROLLBACKS and ABORTS.
"""

import time
import uuid
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

class EventCollector:
    _instance: Optional['EventCollector'] = None
    _lock = threading.Lock()

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.sequence_counter = 0
        self._seq_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'EventCollector':
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def clear(self):
        with self._seq_lock:
            self.events.clear()
            self.transactions.clear()
            self.sequence_counter = 0

    def start_transaction(self, run_id: str, txn_id: str, session_id: str, isolation_level: str) -> Dict[str, Any]:
        with self._seq_lock:
            record = {
                "txn_id": txn_id,
                "run_id": run_id,
                "session_id": session_id,
                "isolation_level": isolation_level,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": None,
                "outcome": "ACTIVE",
                "error_message": None
            }
            self.transactions[txn_id] = record
            return record

    def record_operation(
        self,
        run_id: str,
        txn_id: str,
        session_id: str,
        operation_type: str,
        table_name: str,
        row_id: str,
        old_value: Any = None,
        new_value: Any = None,
        version: Optional[int] = None,
        status: str = "COMPLETED"
    ) -> Dict[str, Any]:
        with self._seq_lock:
            self.sequence_counter += 1
            event = {
                "event_id": f"EVT-{uuid.uuid4().hex[:8].upper()}",
                "run_id": run_id,
                "txn_id": txn_id,
                "session_id": session_id,
                "sequence": self.sequence_counter,
                "operation_type": operation_type.upper(),
                "table_name": table_name,
                "row_id": str(row_id),
                "old_value": str(old_value) if old_value is not None else None,
                "new_value": str(new_value) if new_value is not None else None,
                "version": version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status
            }
            self.events.append(event)
            return event

    def end_transaction(self, txn_id: str, outcome: str = "COMMITTED", error_message: Optional[str] = None):
        with self._seq_lock:
            if txn_id in self.transactions:
                self.transactions[txn_id]["end_time"] = datetime.now(timezone.utc).isoformat()
                self.transactions[txn_id]["outcome"] = outcome
                self.transactions[txn_id]["error_message"] = error_message

    def get_run_events(self, run_id: str) -> List[Dict[str, Any]]:
        with self._seq_lock:
            return [e for e in self.events if e["run_id"] == run_id]

    def get_run_transactions(self, run_id: str) -> List[Dict[str, Any]]:
        with self._seq_lock:
            return [t for t in self.transactions.values() if t["run_id"] == run_id]

event_collector = EventCollector.get_instance()
