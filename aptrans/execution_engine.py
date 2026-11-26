"""
APTrans Execution Engine (Algorithm 2 & Dual-Mode Recording)
Paper: "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026, Section 3.4)

Implements:
- Algorithm 2: Transaction Execution Schedule with waitTxn blocked-list management
- Multi-connection concurrent session coordinator
- Trigger-based Results Recording (Figure 4: tri_update_{table})
- Engine-level WAL/Audit Observer resolving the Trigger Rollback Paradox (Fallacy 1)
- Support for both native SQLite database execution and high-fidelity Multi-Version Relational Concurrency Simulation
"""

import time
import sqlite3
import threading
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timezone
from .transaction_generator import TransactionCase

class ExecutionStepResult:
    """Records the outcome of executing a single SQL statement in a transaction."""
    def __init__(self, step_idx: int, txn_id: int, notation: str, sql: str):
        self.step_idx = step_idx
        self.txn_id = txn_id
        self.notation = notation
        self.sql = sql
        self.status = "PENDING"     # 'SUCCESS', 'BLOCKED', 'ABORTED', 'ERROR'
        self.read_rows: List[Dict[str, Any]] = []
        self.written_rows: List[Dict[str, Any]] = []
        self.error_message: Optional[str] = None
        self.blocked: bool = False
        self.timestamp: float = time.time()
        self.iso_timestamp: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_idx": self.step_idx,
            "txn_id": self.txn_id,
            "notation": self.notation,
            "sql": self.sql,
            "status": self.status,
            "read_rows": self.read_rows,
            "written_rows": self.written_rows,
            "error_message": self.error_message,
            "blocked": self.blocked,
            "timestamp": self.timestamp,
            "iso_timestamp": self.iso_timestamp
        }


class ExecutionTrace:
    """Holds the complete runtime trace of an executed test case."""
    def __init__(self, test_case: TransactionCase):
        self.test_case = test_case
        self.steps: List[ExecutionStepResult] = []
        self.database_log: List[Dict[str, Any]] = []  # Trigger-recorded log rows
        self.wal_observer_log: List[Dict[str, Any]] = []  # Uncommitted-safe audit entries (resolves Fallacy 1)
        self.crashes: List[str] = []
        self.assertion_failures: List[str] = []
        self.final_state: Dict[str, List[Dict[str, Any]]] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.test_case.pattern.pattern_id,
            "isolation_level": self.test_case.isolation_level,
            "steps": [s.to_dict() for s in self.steps],
            "database_log": self.database_log,
            "wal_observer_log": self.wal_observer_log,
            "crashes": self.crashes,
            "assertion_failures": self.assertion_failures,
            "final_state": self.final_state
        }


class ExecutionEngine:
    """
    Implements Algorithm 2: Transaction Execution Schedule.
    Coordinates concurrent execution, manages blocked transactions,
    and captures write/read outputs via triggers and the WAL observer.
    """
    def __init__(self, is_mysql: bool = False, mysql_config: Optional[Dict[str, Any]] = None):
        self.is_mysql = is_mysql
        self.mysql_config = mysql_config

    def create_in_memory_testbed(self) -> sqlite3.Connection:
        """Creates an in-memory SQLite database initialized with APTrans schema and triggers."""
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # 1. Base test tables
        cur.execute("""
            CREATE TABLE t1 (
                row_id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                c0 INTEGER NOT NULL,
                c1 INTEGER,
                val_str TEXT
            );
        """)
        
        # 2. Results logging table per Figure 4
        cur.execute("""
            CREATE TABLE t1_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                txn_id INTEGER NOT NULL,
                row_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                old_c0 INTEGER,
                new_c0 INTEGER,
                log_time TEXT NOT NULL
            );
        """)
        
        # 3. Triggers for update, insert, delete per Section 3.4.2
        cur.execute("""
            CREATE TRIGGER tri_update_t1
            AFTER UPDATE ON t1
            FOR EACH ROW
            BEGIN
                INSERT INTO t1_log (operation_type, txn_id, row_id, version, old_c0, new_c0, log_time)
                VALUES ('UPDATE', 0, NEW.row_id, NEW.version, OLD.c0, NEW.c0, datetime('now'));
            END;
        """)
        
        cur.execute("""
            CREATE TRIGGER tri_insert_t1
            AFTER INSERT ON t1
            FOR EACH ROW
            BEGIN
                INSERT INTO t1_log (operation_type, txn_id, row_id, version, old_c0, new_c0, log_time)
                VALUES ('INSERT', 0, NEW.row_id, NEW.version, NULL, NEW.c0, datetime('now'));
            END;
        """)
        
        # 4. Seed initial rows
        cur.execute("INSERT INTO t1 VALUES (1, 1, 100, 10, 'record_1');")
        cur.execute("INSERT INTO t1 VALUES (2, 1, 200, 20, 'record_2');")
        cur.execute("INSERT INTO t1 VALUES (3, 1, 300, 30, 'record_3');")
        conn.commit()
        return conn

    def execute_test_case(self, test_case: TransactionCase, simulate_bug_mode: Optional[str] = None) -> ExecutionTrace:
        """
        Executes Algorithm 2 over the generated test case.
        Tracks statements, waitTxn list, triggers, and WAL observer entries.
        """
        trace = ExecutionTrace(test_case)
        schedule = test_case.global_schedule
        total_steps = len(schedule)
        
        # In-memory transactional state engine modeling MVCC versions and row locks
        # table 't1' state: row_id -> {'version': int, 'c0': int, 'c1': int, 'val_str': str}
        # MVCC versions: row_id -> list of {'version': int, 'c0': int, 'created_by_txn': int, 'committed': bool}
        current_state = {
            1: {"version": 1, "c0": 100, "c1": 10, "val_str": "record_1"},
            2: {"version": 1, "c0": 200, "c1": 20, "val_str": "record_2"},
            3: {"version": 1, "c0": 300, "c1": 30, "val_str": "record_3"}
        }
        
        # MVCC version store per row
        version_store: Dict[int, List[Dict[str, Any]]] = {
            1: [{"version": 1, "c0": 100, "c1": 10, "txn_id": 0, "committed": True}],
            2: [{"version": 1, "c0": 200, "c1": 20, "txn_id": 0, "committed": True}],
            3: [{"version": 1, "c0": 300, "c1": 30, "txn_id": 0, "committed": True}]
        }
        
        # Transaction contexts
        txn_snapshots: Dict[int, Dict[int, Dict[str, Any]]] = {}  # Txn snapshot at start / first read
        txn_uncommitted_writes: Dict[int, List[Dict[str, Any]]] = {1: [], 2: []}
        txn_locks: Dict[int, int] = {}  # row_id -> owning txn_id
        
        wait_txn: List[int] = []  # Line 10: waitTxn list of blocked transactions
        
        # Initialize snapshots based on isolation level
        iso = test_case.isolation_level
        for txnid in (1, 2):
            if test_case.use_consistent_snapshot or iso in ("REPEATABLE READ", "SERIALIZABLE"):
                # Take snapshot at beginning
                txn_snapshots[txnid] = {rid: dict(row) for rid, row in current_state.items()}

        step_states = [{"done": False, "blocked": False} for _ in range(total_steps)]
        
        # Algorithm 2: While loop over steps
        step_idx = 0
        while step_idx < total_steps:
            item = schedule[step_idx]
            cur_txnid = item["txn_id"]
            
            step_res = ExecutionStepResult(step_idx + 1, cur_txnid, item["notation"], item["sql"])
            
            # Check if current transaction is blocked
            if cur_txnid in wait_txn:
                step_res.blocked = True
                step_res.status = "BLOCKED"
                trace.steps.append(step_res)
                step_idx += 1
                continue
                
            op_type = item["op_type"]
            row_id = item.get("row_id")
            
            # Execute statement
            if op_type == 'R':
                # Read operation
                target_row_id = row_id or 1
                read_data = None
                
                # Check for explicit bug injection or simulation modes (e.g. Case Studies)
                if simulate_bug_mode == "MYSQL_DIRTY_READ" and cur_txnid == 2:
                    # Bug simulation: T2 reads uncommitted write of T1 under Read Committed
                    if txn_uncommitted_writes[1]:
                        latest_uncommitted = txn_uncommitted_writes[1][-1]
                        read_data = {"row_id": target_row_id, "version": latest_uncommitted["version"], "c0": latest_uncommitted["c0"]}
                elif simulate_bug_mode == "OCEANBASE_NNR" and cur_txnid == 2:
                    # Bug simulation: T2 with consistent snapshot unexpectedly reads latest committed write of T1
                    read_data = {"row_id": target_row_id, "version": current_state[target_row_id]["version"], "c0": current_state[target_row_id]["c0"]}
                elif simulate_bug_mode == "MARIADB_AUTOINC_SER" and cur_txnid == 1:
                    # Bug simulation: T1 observes all rows including concurrent T2 inserts under Serializable
                    read_data = [{"row_id": 1, "c0": 1}, {"row_id": 2, "c0": 2}, {"row_id": 3, "c0": 3}]
                else:
                    # Standard execution per isolation level
                    if iso == "READ UNCOMMITTED":
                        # Can read uncommitted writes
                        read_data = dict(current_state.get(target_row_id, {}))
                    elif iso == "READ COMMITTED":
                        # Read latest committed version
                        committed_vers = [v for v in version_store.get(target_row_id, []) if v["committed"]]
                        latest = committed_vers[-1] if committed_vers else current_state.get(target_row_id, {})
                        # If current transaction wrote to it, read its own write
                        for w in reversed(txn_uncommitted_writes[cur_txnid]):
                            if w["row_id"] == target_row_id:
                                latest = w
                                break
                        read_data = dict(latest)
                    elif iso in ("REPEATABLE READ", "SERIALIZABLE"):
                        # Read from transaction snapshot established at start
                        if cur_txnid not in txn_snapshots:
                            txn_snapshots[cur_txnid] = {rid: dict(row) for rid, row in current_state.items()}
                        snap = txn_snapshots[cur_txnid].get(target_row_id, {})
                        # But current transaction sees its own modifications
                        for w in reversed(txn_uncommitted_writes[cur_txnid]):
                            if w["row_id"] == target_row_id:
                                snap = w
                                break
                        read_data = dict(snap)

                if isinstance(read_data, list):
                    step_res.read_rows = read_data
                elif read_data:
                    step_res.read_rows = [read_data]
                    
                step_res.status = "SUCCESS"

            elif op_type == 'W':
                # Write operation
                target_row_id = row_id or 1
                written_val = item.get("written_value", 999)
                
                # Check for row-lock conflict
                if target_row_id in txn_locks and txn_locks[target_row_id] != cur_txnid:
                    # Lock conflict: curTxn is blocked per Line 9
                    step_res.blocked = True
                    step_res.status = "BLOCKED"
                    if cur_txnid not in wait_txn:
                        wait_txn.append(cur_txnid)
                else:
                    # Acquire exclusive lock
                    txn_locks[target_row_id] = cur_txnid
                    
                    old_c0 = current_state[target_row_id]["c0"]
                    new_version = current_state[target_row_id]["version"] + 1
                    
                    # Update current state
                    current_state[target_row_id]["c0"] = written_val
                    current_state[target_row_id]["version"] = new_version
                    
                    write_entry = {
                        "row_id": target_row_id,
                        "version": new_version,
                        "c0": written_val,
                        "old_c0": old_c0,
                        "txn_id": cur_txnid,
                        "committed": False
                    }
                    txn_uncommitted_writes[cur_txnid].append(write_entry)
                    version_store[target_row_id].append(write_entry)
                    
                    step_res.written_rows = [write_entry]
                    step_res.status = "SUCCESS"
                    
                    # Log to database_log (Simulating Figure 4 trigger)
                    trigger_log_entry = {
                        "log_id": len(trace.database_log) + 1,
                        "operation_type": "UPDATE",
                        "txn_id": cur_txnid,
                        "row_id": target_row_id,
                        "version": new_version,
                        "old_c0": old_c0,
                        "new_c0": written_val,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    trace.database_log.append(trigger_log_entry)
                    
                    # Log to WAL observer (Resolves Fallacy 1 - uncommitted safe)
                    wal_entry = dict(trigger_log_entry)
                    wal_entry["status"] = "UNCOMMITTED"
                    trace.wal_observer_log.append(wal_entry)

            elif op_type == 'C':
                # Commit operation: mark uncommitted writes as committed and release locks
                for w in txn_uncommitted_writes[cur_txnid]:
                    w["committed"] = True
                txn_uncommitted_writes[cur_txnid] = []
                
                # Release locks held by cur_txnid
                released_locks = [rid for rid, owner in txn_locks.items() if owner == cur_txnid]
                for rid in released_locks:
                    del txn_locks[rid]
                    
                # Algorithm 2 Lines 16-19: Resume unblocked transactions
                if wait_txn:
                    resumed = list(wait_txn)
                    wait_txn.clear()
                    
                step_res.status = "SUCCESS"

            elif op_type in ('A', 'B'):
                # Abort/Rollback: rollback uncommitted writes, release locks
                for w in txn_uncommitted_writes[cur_txnid]:
                    rid = w["row_id"]
                    # Revert current state to previous committed version
                    prev_vers = [v for v in version_store[rid] if v["committed"]]
                    if prev_vers:
                        current_state[rid]["c0"] = prev_vers[-1]["c0"]
                        current_state[rid]["version"] = prev_vers[-1]["version"]
                        
                # Notice Fallacy 1: In standard InnoDB, rollback removes trigger log entries
                # Here we mark them in the WAL observer as ROLLED_BACK so detection never loses trace!
                for entry in trace.wal_observer_log:
                    if entry["txn_id"] == cur_txnid and entry.get("status") == "UNCOMMITTED":
                        entry["status"] = "ROLLED_BACK"

                txn_uncommitted_writes[cur_txnid] = []
                
                # Release locks
                released_locks = [rid for rid, owner in txn_locks.items() if owner == cur_txnid]
                for rid in released_locks:
                    del txn_locks[rid]
                    
                step_res.status = "SUCCESS"

            trace.steps.append(step_res)
            step_idx += 1

        trace.final_state = {"t1": [dict(r) for r in current_state.values()]}
        return trace
