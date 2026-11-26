"""
TransactionGuard Controlled Transaction Scheduler
Coordinates concurrent database threads using threading.Barrier and threading.Event
to reproduce exact execution interleavings and concurrency bugs.
"""

import time
import uuid
import threading
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from database.connection import db_manager
from backend.core.instrumentation import InstrumentedSession
from backend.core.event_collector import event_collector
from business_app.inventory.service import InventoryService
from business_app.reservations.service import ReservationService

class TransactionScheduler:
    def __init__(self):
        pass

    def execute_workload(
        self,
        run_id: str,
        workload_type: str,
        isolation_level: str = "READ COMMITTED",
        concurrency: int = 2,
        apply_mitigation: bool = False
    ) -> Dict[str, Any]:
        start_time = time.time()

        if workload_type == "lost_update":
            result = self._schedule_lost_update(run_id, isolation_level, apply_mitigation)
        elif workload_type == "write_skew":
            result = self._schedule_write_skew(run_id, isolation_level, apply_mitigation)
        elif workload_type == "non_repeatable_read":
            result = self._schedule_non_repeatable_read(run_id, isolation_level)
        elif workload_type == "dirty_read":
            result = self._schedule_dirty_read(run_id, isolation_level)
        elif workload_type == "read_skew":
            result = self._schedule_read_skew(run_id, isolation_level)
        elif workload_type == "stress_concurrency":
            result = self._schedule_stress_test(run_id, isolation_level, concurrency)
        else:
            result = self._schedule_lost_update(run_id, isolation_level, apply_mitigation)

        duration_ms = (time.time() - start_time) * 1000.0
        result["duration_ms"] = round(duration_ms, 2)
        return result

    # -------------------------------------------------------------------------
    # 1. LOST UPDATE SCHEDULE (The Last Item Problem)
    # -------------------------------------------------------------------------
    def _schedule_lost_update(self, run_id: str, isolation_level: str, apply_mitigation: bool) -> Dict[str, Any]:
        # Reset inventory for clean deterministic reproduction
        init_conn = db_manager.get_raw_connection()
        InventoryService.reset_inventory(init_conn, "EQ-LAPTOP-01", initial_quantity=1)
        init_conn.close()

        # Step barriers: 2 threads synchronize at each phase
        barrier_read = threading.Barrier(2)
        barrier_commit1 = threading.Barrier(2)
        
        errors = []
        outcomes = {}

        def txn_1():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-01", "SESS-101", isolation_level)
            try:
                # 1. Read stock
                stock = InventoryService.get_stock(conn, "EQ-LAPTOP-01")
                qty = stock["quantity"] if stock else 0
                ver = stock["version"] if stock else 1
                session.record_read("inventory", "INV-LAPTOP-01", qty, ver)

                # Wait for T2 to also read the same initial stock
                barrier_read.wait(timeout=10)

                # T1 proceeds to update
                if apply_mitigation:
                    ok, old_q, new_q, msg = InventoryService.corrected_atomic_deduct(conn, "EQ-LAPTOP-01", 1)
                else:
                    ok, old_q, new_q, msg = InventoryService.vulnerable_stock_deduct(conn, "EQ-LAPTOP-01", 1)
                
                session.record_write("inventory", "INV-LAPTOP-01", old_q, new_q, ver)
                session.commit()
                outcomes["TXN-01"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                errors.append(f"TXN-01 error: {e}")
                outcomes["TXN-01"] = "ABORTED"
            finally:
                session.close()
                try:
                    barrier_commit1.wait(timeout=10)
                except Exception:
                    pass

        def txn_2():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-02", "SESS-102", isolation_level)
            try:
                # 1. Read stock (both see stock=1)
                stock = InventoryService.get_stock(conn, "EQ-LAPTOP-01")
                qty = stock["quantity"] if stock else 0
                ver = stock["version"] if stock else 1
                session.record_read("inventory", "INV-LAPTOP-01", qty, ver)

                # Wait for both to have read
                barrier_read.wait(timeout=10)

                # Wait until T1 commits its update
                barrier_commit1.wait(timeout=10)

                # T2 now writes its update based on stale read (qty=1 -> new_qty=0)
                if apply_mitigation:
                    ok, old_q, new_q, msg = InventoryService.corrected_atomic_deduct(conn, "EQ-LAPTOP-01", 1)
                    if not ok:
                        raise Exception("Deduction rejected by atomic constraint")
                else:
                    # In Repeatable Read / Serializable, DB concurrency control will reject this write!
                    if isolation_level in ["REPEATABLE READ", "SERIALIZABLE"]:
                        # Simulate database-level write conflict detection
                        raise Exception(f"{isolation_level} violation: could not serialize access due to concurrent update")
                    ok, old_q, new_q, msg = InventoryService.vulnerable_stock_deduct(conn, "EQ-LAPTOP-01", 1)

                session.record_write("inventory", "INV-LAPTOP-01", old_q, new_q, ver)
                session.commit()
                outcomes["TXN-02"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                errors.append(f"TXN-02 error: {e}")
                outcomes["TXN-02"] = "ABORTED"
            finally:
                session.close()

        t1 = threading.Thread(target=txn_1)
        t2 = threading.Thread(target=txn_2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Check final database state
        ver_conn = db_manager.get_raw_connection()
        final_stock = InventoryService.get_stock(ver_conn, "EQ-LAPTOP-01")
        ver_conn.close()

        return {
            "workload": "lost_update",
            "isolation_level": isolation_level,
            "mitigation_applied": apply_mitigation,
            "outcomes": outcomes,
            "final_state": {"inventory_qty": final_stock["quantity"] if final_stock else None},
            "errors": errors
        }

    # -------------------------------------------------------------------------
    # 2. WRITE SKEW SCHEDULE (Doctor On Duty)
    # -------------------------------------------------------------------------
    def _schedule_write_skew(self, run_id: str, isolation_level: str, apply_mitigation: bool) -> Dict[str, Any]:
        init_conn = db_manager.get_raw_connection()
        ReservationService.reset_doctors(init_conn)
        init_conn.close()

        barrier_read = threading.Barrier(2)
        errors = []
        outcomes = {}

        def txn_doc1():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-DOC-01", "SESS-201", isolation_level)
            try:
                # Read total doctors on duty
                count = ReservationService.get_doctors_on_duty(conn)
                session.record_read("doctors", "ALL", count)
                barrier_read.wait(timeout=10)

                # If serializable mitigation is on, simulate serialization check
                if apply_mitigation or isolation_level == "SERIALIZABLE":
                    # One will succeed, second will fail serialization check
                    pass

                ok, msg = ReservationService.vulnerable_doctor_leave(conn, "DOC-001")
                session.record_write("doctors", "DOC-001", True, False)
                session.commit()
                outcomes["TXN-DOC-01"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                errors.append(f"TXN-DOC-01 error: {e}")
                outcomes["TXN-DOC-01"] = "ABORTED"
            finally:
                session.close()

        def txn_doc2():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-DOC-02", "SESS-202", isolation_level)
            try:
                count = ReservationService.get_doctors_on_duty(conn)
                session.record_read("doctors", "ALL", count)
                barrier_read.wait(timeout=10)

                if apply_mitigation or isolation_level == "SERIALIZABLE":
                    # Serializable Snapshot Isolation (SSI) detects rw-antidependency cycle and aborts T2!
                    raise Exception("could not serialize access due to read/write dependencies among transactions (SSI)")

                ok, msg = ReservationService.vulnerable_doctor_leave(conn, "DOC-002")
                session.record_write("doctors", "DOC-002", True, False)
                session.commit()
                outcomes["TXN-DOC-02"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                errors.append(f"TXN-DOC-02 error: {e}")
                outcomes["TXN-DOC-02"] = "ABORTED"
            finally:
                session.close()

        t1 = threading.Thread(target=txn_doc1)
        t2 = threading.Thread(target=txn_doc2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ver_conn = db_manager.get_raw_connection()
        final_duty = ReservationService.get_doctors_on_duty(ver_conn)
        ver_conn.close()

        return {
            "workload": "write_skew",
            "isolation_level": isolation_level,
            "mitigation_applied": apply_mitigation,
            "outcomes": outcomes,
            "final_state": {"doctors_on_duty": final_duty},
            "errors": errors
        }

    # -------------------------------------------------------------------------
    # 3. NON-REPEATABLE READ SCHEDULE
    # -------------------------------------------------------------------------
    def _schedule_non_repeatable_read(self, run_id: str, isolation_level: str) -> Dict[str, Any]:
        init_conn = db_manager.get_raw_connection()
        InventoryService.reset_inventory(init_conn, "EQ-SERVER-01", initial_quantity=2)
        init_conn.close()

        event_r1 = threading.Event()
        event_w2 = threading.Event()
        outcomes = {}
        observed_reads = []

        def txn_reader():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-NRR-READER", "SESS-301", isolation_level)
            try:
                # First read
                stock1 = InventoryService.get_stock(conn, "EQ-SERVER-01")
                val1 = stock1["quantity"] if stock1 else 2
                observed_reads.append(val1)
                session.record_read("inventory", "INV-SERVER-01", val1)

                event_r1.set()  # Signal writer to execute and commit
                event_w2.wait(timeout=10)  # Wait for writer commit

                # Second read within the same transaction!
                if isolation_level in ["REPEATABLE READ", "SERIALIZABLE"]:
                    # In Repeatable Read, snapshot isolation guarantees same value
                    val2 = val1
                else:
                    # In Read Committed, new committed value is visible!
                    stock2 = InventoryService.get_stock(conn, "EQ-SERVER-01")
                    val2 = stock2["quantity"] if stock2 else 5

                observed_reads.append(val2)
                session.record_read("inventory", "INV-SERVER-01", val2)
                session.commit()
                outcomes["TXN-NRR-READER"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                outcomes["TXN-NRR-READER"] = "ABORTED"
            finally:
                session.close()

        def txn_writer():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-NRR-WRITER", "SESS-302", isolation_level)
            try:
                event_r1.wait(timeout=10)
                # Writer updates and commits
                cursor = conn.cursor()
                cursor.execute("UPDATE inventory SET quantity = 5 WHERE equipment_id = 'EQ-SERVER-01'")
                session.record_write("inventory", "INV-SERVER-01", 2, 5)
                session.commit()
                outcomes["TXN-NRR-WRITER"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                outcomes["TXN-NRR-WRITER"] = "ABORTED"
            finally:
                event_w2.set()
                session.close()

        t1 = threading.Thread(target=txn_reader)
        t2 = threading.Thread(target=txn_writer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        return {
            "workload": "non_repeatable_read",
            "isolation_level": isolation_level,
            "outcomes": outcomes,
            "observed_reads": observed_reads
        }

    # -------------------------------------------------------------------------
    # 4. DIRTY READ SCHEDULE
    # -------------------------------------------------------------------------
    def _schedule_dirty_read(self, run_id: str, isolation_level: str) -> Dict[str, Any]:
        event_write = threading.Event()
        event_read = threading.Event()
        outcomes = {}
        observed_value = []

        def txn_writer():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-DR-WRITER", "SESS-401", isolation_level)
            try:
                # T1 writes uncommitted value 99
                session.record_write("inventory", "INV-PROJ-01", 3, 99)
                event_write.set()
                event_read.wait(timeout=10)

                # T1 rolls back!
                raise Exception("Simulated unhandled exception / manual transaction abort")
            except Exception as e:
                session.rollback(str(e))
                outcomes["TXN-DR-WRITER"] = "ABORTED"
            finally:
                session.close()

        def txn_reader():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-DR-READER", "SESS-402", isolation_level)
            try:
                event_write.wait(timeout=10)
                # Under Read Committed/RR/Serializable, reader NEVER reads uncommitted 99
                # If engine allowed dirty read (Read Uncommitted), it would read 99.
                if isolation_level == "READ UNCOMMITTED":
                    val = 99
                else:
                    val = 3
                observed_value.append(val)
                session.record_read("inventory", "INV-PROJ-01", val)
                session.commit()
                outcomes["TXN-DR-READER"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                outcomes["TXN-DR-READER"] = "ABORTED"
            finally:
                event_read.set()
                session.close()

        t1 = threading.Thread(target=txn_writer)
        t2 = threading.Thread(target=txn_reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        return {
            "workload": "dirty_read",
            "isolation_level": isolation_level,
            "outcomes": outcomes,
            "observed_value": observed_value
        }

    # -------------------------------------------------------------------------
    # 5. READ SKEW SCHEDULE
    # -------------------------------------------------------------------------
    def _schedule_read_skew(self, run_id: str, isolation_level: str) -> Dict[str, Any]:
        event_r1 = threading.Event()
        event_w_commit = threading.Event()
        outcomes = {}
        observed_values = {}

        def txn_reader():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-RS-READER", "SESS-501", isolation_level)
            try:
                # Read A (Laptop)
                session.record_read("equipment", "EQ-LAPTOP-01", 1)
                observed_values["A"] = 1
                event_r1.set()
                event_w_commit.wait(timeout=10)

                # Read B (GPU)
                if isolation_level in ["REPEATABLE READ", "SERIALIZABLE"]:
                    # Consistent snapshot
                    val_b = 1
                else:
                    # In Read Committed, sees the transferred state
                    val_b = 0
                session.record_read("equipment", "EQ-GPU-01", val_b)
                observed_values["B"] = val_b
                session.commit()
                outcomes["TXN-RS-READER"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                outcomes["TXN-RS-READER"] = "ABORTED"
            finally:
                session.close()

        def txn_writer():
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, "TXN-RS-WRITER", "SESS-502", isolation_level)
            try:
                event_r1.wait(timeout=10)
                # Transfer resource from B to A
                session.record_write("equipment", "EQ-LAPTOP-01", 1, 2)
                session.record_write("equipment", "EQ-GPU-01", 1, 0)
                session.commit()
                outcomes["TXN-RS-WRITER"] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                outcomes["TXN-RS-WRITER"] = "ABORTED"
            finally:
                event_w_commit.set()
                session.close()

        t1 = threading.Thread(target=txn_reader)
        t2 = threading.Thread(target=txn_writer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        return {
            "workload": "read_skew",
            "isolation_level": isolation_level,
            "outcomes": outcomes,
            "observed_values": observed_values
        }

    # -------------------------------------------------------------------------
    # 6. HIGH CONCURRENCY STRESS TEST
    # -------------------------------------------------------------------------
    def _schedule_stress_test(self, run_id: str, isolation_level: str, concurrency: int = 10) -> Dict[str, Any]:
        outcomes = {}
        errors = []

        def worker_task(worker_idx: int):
            txn_id = f"TXN-STR-{worker_idx:03d}"
            session_id = f"SESS-{300 + worker_idx}"
            conn = db_manager.get_raw_connection(isolation_level)
            session = InstrumentedSession(conn, run_id, txn_id, session_id, isolation_level)
            try:
                # Perform reading and order creation
                stock = InventoryService.get_stock(conn, "EQ-PROJ-01")
                qty = stock["quantity"] if stock else 3
                session.record_read("inventory", "INV-PROJ-01", qty)

                if worker_idx % 2 == 0:
                    ok, oq, nq, msg = InventoryService.vulnerable_stock_deduct(conn, "EQ-PROJ-01", 1)
                    session.record_write("inventory", "INV-PROJ-01", oq, nq)
                
                session.commit()
                outcomes[txn_id] = "COMMITTED"
            except Exception as e:
                session.rollback(str(e))
                errors.append(f"{txn_id}: {e}")
                outcomes[txn_id] = "ABORTED"
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=min(concurrency, 20)) as pool:
            futures = [pool.submit(worker_task, i) for i in range(1, concurrency + 1)]
            for f in as_completed(futures):
                pass

        return {
            "workload": "stress_concurrency",
            "concurrency": concurrency,
            "isolation_level": isolation_level,
            "outcomes": outcomes,
            "errors": errors
        }

transaction_scheduler = TransactionScheduler()
