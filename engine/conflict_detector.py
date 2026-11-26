"""
DBGuard Conflict Detection & Simulation Engine
Simulates and prevents:
1. Lost Updates (Unsafe, Pessimistic SELECT FOR UPDATE, Optimistic Versioning, Atomic)
2. Double Booking / Duplicate Reservation
3. Cross-Transaction Deadlocks with Wait-For Cycle Detection and Auto-Retry
"""

import time
import threading
from db.database import get_sqlite_connection, DB_LOCK, record_conflict, log_audit
from engine.lock_manager import LockManager, DeadlockException
from engine.transaction_manager import TransactionManager
from engine.integrity_validator import IntegrityValidator, IntegrityViolationException
from engine.recovery_manager import RecoveryManager

class ConflictDetector:
    def __init__(self):
        self.lock_mgr = LockManager()
        self.tx_mgr = TransactionManager()

    # =========================================================================
    # 1. LOST UPDATE SCENARIO
    # =========================================================================
    def run_lost_update(self, mode="unsafe", account_id=1, deduct_t1=100.0, deduct_t2=200.0, user_id=1):
        """
        Runs Lost Update anomaly simulation in specified mode:
        - 'unsafe': Read-Modify-Write race condition (causes $100 loss)
        - 'pessimistic': Row-level locking (SELECT ... FOR UPDATE)
        - 'optimistic': Version column matching (WHERE version = :v)
        - 'atomic': In-engine atomic decrement (UPDATE ... SET balance = balance - X)
        """
        # Ensure account exists and reset to known initial balance ($1000.00)
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT balance, version FROM demo_accounts WHERE account_id = ?;", (account_id,))
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO demo_accounts (account_id, account_number, holder_name, balance, version) VALUES (?, ?, ?, ?, ?);",
                            (account_id, f"ACC-{account_id:04d}", "Alice Johnson", 1000.00, 1))
                conn.commit()
                initial_balance = 1000.00
                initial_version = 1
            else:
                initial_balance = float(row["balance"])
                initial_version = int(row["version"])
            conn.close()

        expected_final = initial_balance - deduct_t1 - deduct_t2
        timeline = []

        if mode == "unsafe":
            result = self._simulate_unsafe_lost_update(account_id, initial_balance, deduct_t1, deduct_t2, user_id, timeline)
        elif mode == "pessimistic":
            result = self._simulate_pessimistic_lost_update(account_id, initial_balance, deduct_t1, deduct_t2, user_id, timeline)
        elif mode == "optimistic":
            result = self._simulate_optimistic_lost_update(account_id, initial_balance, initial_version, deduct_t1, deduct_t2, user_id, timeline)
        elif mode == "atomic":
            result = self._simulate_atomic_lost_update(account_id, initial_balance, deduct_t1, deduct_t2, user_id, timeline)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        result["initial_balance"] = initial_balance
        result["expected_final"] = expected_final
        result["timeline"] = timeline
        return result

    def _simulate_unsafe_lost_update(self, account_id, initial_balance, deduct_t1, deduct_t2, user_id, timeline):
        tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Unsafe)", thread_tag="T1")
        tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Unsafe)", thread_tag="T2")

        # Step 1: Thread 1 reads balance
        t1_read = initial_balance
        timeline.append(tx1.record_step("T1", "READ", f"demo_accounts:{account_id}", f"Read balance = ${t1_read:.2f}", "SUCCESS"))

        # Step 2: Thread 2 reads balance concurrently (Unsafe: sees same initial balance!)
        t2_read = initial_balance
        timeline.append(tx2.record_step("T2", "READ", f"demo_accounts:{account_id}", f"Read balance = ${t2_read:.2f} (Concurrent read without lock)", "SUCCESS"))

        # Step 3: Thread 1 computes and writes
        t1_new = t1_read - deduct_t1
        timeline.append(tx1.record_step("T1", "CALCULATE", f"demo_accounts:{account_id}", f"Compute ${t1_read:.2f} - ${deduct_t1:.2f} = ${t1_new:.2f}", "SUCCESS"))

        with DB_LOCK:
            conn = get_sqlite_connection()
            conn.execute("UPDATE demo_accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = ?;", (t1_new, account_id))
            conn.commit()
            conn.close()

        timeline.append(tx1.record_step("T1", "WRITE", f"demo_accounts:{account_id}", f"Wrote balance = ${t1_new:.2f}", "SUCCESS"))
        self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")
        timeline.append(tx1.record_step("T1", "COMMIT", f"demo_accounts:{account_id}", "Committed $900.00", "COMMITTED"))

        # Step 4: Thread 2 computes using its stale read ($1000 - $200 = $800) and writes, overwriting T1!
        t2_new = t2_read - deduct_t2
        timeline.append(tx2.record_step("T2", "CALCULATE", f"demo_accounts:{account_id}", f"Compute with stale read: ${t2_read:.2f} - ${deduct_t2:.2f} = ${t2_new:.2f}", "WARNING"))

        with DB_LOCK:
            conn = get_sqlite_connection()
            conn.execute("UPDATE demo_accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = ?;", (t2_new, account_id))
            conn.commit()
            conn.close()

        timeline.append(tx2.record_step("T2", "WRITE", f"demo_accounts:{account_id}", f"Overwrote balance = ${t2_new:.2f} (T1 write lost!)", "WARNING"))
        self.tx_mgr.commit(tx2.tx_id, thread_tag="T2")
        timeline.append(tx2.record_step("T2", "COMMIT", f"demo_accounts:{account_id}", "Committed $800.00", "COMMITTED"))

        final_balance = t2_new
        data_loss = deduct_t1  # $100.00 lost

        # Record conflict in DBGuard system tables
        conflict_details = {
            "mode": "unsafe",
            "account_id": account_id,
            "t1_deduct": deduct_t1,
            "t2_deduct": deduct_t2,
            "expected_balance": initial_balance - deduct_t1 - deduct_t2,
            "actual_balance": final_balance,
            "data_loss": data_loss,
            "anomaly_explanation": f"Lost Update Anomaly: T2 overwritten T1's deduction. Expected ${initial_balance - deduct_t1 - deduct_t2:.2f}, got ${final_balance:.2f}. Lost ${data_loss:.2f}."
        }
        record_conflict(
            transaction_id=tx2.tx_id,
            conflict_type="LOST_UPDATE",
            severity="HIGH",
            resolution_status="DETECTED_CORRUPTED",
            details=conflict_details
        )
        log_audit("LOST_UPDATE_ANOMALY_DETECTED", "WARNING", user_id=user_id, payload_summary=conflict_details["anomaly_explanation"])

        return {
            "mode": "unsafe",
            "success": True,
            "anomaly_detected": True,
            "final_balance": final_balance,
            "data_loss": data_loss,
            "message": f"CONFLICT DETECTED: Lost Update Anomaly! Expected balance: ${initial_balance - deduct_t1 - deduct_t2:.2f}, Actual: ${final_balance:.2f}. Data Loss: ${data_loss:.2f}."
        }

    def _simulate_pessimistic_lost_update(self, account_id, initial_balance, deduct_t1, deduct_t2, user_id, timeline):
        tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Pessimistic)", thread_tag="T1")
        tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Pessimistic)", thread_tag="T2")
        res_key = f"demo_accounts:{account_id}"

        # Step 1: Thread 1 acquires exclusive lock (SELECT ... FOR UPDATE)
        self.lock_mgr.acquire_lock(res_key, tx1.tx_id, mode="EXCLUSIVE")
        timeline.append(tx1.record_step("T1", "SELECT ... FOR UPDATE", res_key, f"Acquired exclusive row lock on {res_key}", "SUCCESS"))

        t1_read = initial_balance
        timeline.append(tx1.record_step("T1", "READ", res_key, f"Read balance = ${t1_read:.2f}", "SUCCESS"))

        # Step 2: Thread 2 attempts SELECT ... FOR UPDATE on same row
        # In multi-threaded execution, T2 would block. Here we simulate T2 waiting for T1 to commit.
        timeline.append(tx2.record_step("T2", "SELECT ... FOR UPDATE", res_key, f"Attempting row lock on {res_key} -> Blocked by T1", "LOCK_WAIT"))

        # Step 3: Thread 1 computes and writes
        t1_new = t1_read - deduct_t1
        timeline.append(tx1.record_step("T1", "UPDATE", res_key, f"Set balance = ${t1_new:.2f}", "SUCCESS"))

        with DB_LOCK:
            conn = get_sqlite_connection()
            conn.execute("UPDATE demo_accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = ?;", (t1_new, account_id))
            conn.commit()
            conn.close()

        self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")
        timeline.append(tx1.record_step("T1", "COMMIT", res_key, f"Committed ${t1_new:.2f}. Row lock released.", "COMMITTED"))

        # Step 4: Now Thread 2 unblocks, acquires row lock, reads freshly committed balance
        self.lock_mgr.acquire_lock(res_key, tx2.tx_id, mode="EXCLUSIVE")
        timeline.append(tx2.record_step("T2", "LOCK_ACQUIRED", res_key, f"Lock acquired after wait (wait_ms=12.4ms)", "SUCCESS", wait_ms=12.4))

        t2_read = t1_new  # Fresh read ($900)
        timeline.append(tx2.record_step("T2", "READ", res_key, f"Read current serialized balance = ${t2_read:.2f}", "SUCCESS"))

        t2_new = t2_read - deduct_t2
        timeline.append(tx2.record_step("T2", "UPDATE", res_key, f"Set balance = ${t2_new:.2f}", "SUCCESS"))

        with DB_LOCK:
            conn = get_sqlite_connection()
            conn.execute("UPDATE demo_accounts SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE account_id = ?;", (t2_new, account_id))
            conn.commit()
            conn.close()

        self.tx_mgr.commit(tx2.tx_id, thread_tag="T2")
        timeline.append(tx2.record_step("T2", "COMMIT", res_key, f"Committed ${t2_new:.2f}. Lock released.", "COMMITTED"))

        final_balance = t2_new
        data_loss = 0.00

        record_conflict(
            transaction_id=tx2.tx_id,
            conflict_type="LOST_UPDATE",
            severity="LOW",
            resolution_status="PREVENTED_PESSIMISTIC",
            details={
                "mode": "pessimistic",
                "lock_type": "EXCLUSIVE (SELECT ... FOR UPDATE)",
                "final_balance": final_balance,
                "data_loss": 0.00,
                "message": "Pessimistic lock forced T2 into LOCK_WAIT until T1 committed, preventing lost update."
            }
        )
        log_audit("PESSIMISTIC_LOCK_ENFORCED", "SUCCESS", user_id=user_id, payload_summary=f"Lost update prevented. Serialized final balance: ${final_balance:.2f}.")

        return {
            "mode": "pessimistic",
            "success": True,
            "anomaly_detected": False,
            "final_balance": final_balance,
            "data_loss": data_loss,
            "message": f"SUCCESS: Transaction serialized safely via SELECT ... FOR UPDATE. Final balance: ${final_balance:.2f}."
        }

    def _simulate_optimistic_lost_update(self, account_id, initial_balance, initial_version, deduct_t1, deduct_t2, user_id, timeline):
        tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Optimistic)", thread_tag="T1")
        tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Optimistic)", thread_tag="T2")
        res_key = f"demo_accounts:{account_id}"

        # Both read balance and current version
        v1 = initial_version
        timeline.append(tx1.record_step("T1", "READ", res_key, f"Read balance=${initial_balance:.2f}, version={v1}", "SUCCESS"))
        timeline.append(tx2.record_step("T2", "READ", res_key, f"Read balance=${initial_balance:.2f}, version={v1}", "SUCCESS"))

        # T1 commits first
        t1_new = initial_balance - deduct_t1
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("UPDATE demo_accounts SET balance = ?, version = version + 1 WHERE account_id = ? AND version = ?;",
                        (t1_new, account_id, v1))
            rows_affected = cur.rowcount
            conn.commit()
            conn.close()

        timeline.append(tx1.record_step("T1", "UPDATE WHERE version=1", res_key, f"Updated balance=${t1_new:.2f}, rows_affected={rows_affected}", "SUCCESS"))
        self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")
        timeline.append(tx1.record_step("T1", "COMMIT", res_key, "Committed version 2", "COMMITTED"))

        # T2 attempts update with old version (version=1)
        t2_new_stale = initial_balance - deduct_t2
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("UPDATE demo_accounts SET balance = ?, version = version + 1 WHERE account_id = ? AND version = ?;",
                        (t2_new_stale, account_id, v1))
            rows_affected_t2 = cur.rowcount
            conn.commit()
            conn.close()

        timeline.append(tx2.record_step("T2", "UPDATE WHERE version=1", res_key, f"rows_affected={rows_affected_t2} (Optimistic Conflict Detected!)", "WARNING"))

        # T2 detects rows_affected == 0, triggers automatic optimistic retry
        timeline.append(tx2.record_step("T2", "OPTIMISTIC_RETRY", res_key, "Version mismatch detected! Re-reading latest committed state...", "RUNNING"))

        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT balance, version FROM demo_accounts WHERE account_id = ?;", (account_id,))
            latest = cur.fetchone()
            latest_balance = float(latest["balance"])
            latest_version = int(latest["version"])

            # Compute with latest balance and update with latest_version
            t2_final = latest_balance - deduct_t2
            cur.execute("UPDATE demo_accounts SET balance = ?, version = version + 1 WHERE account_id = ? AND version = ?;",
                        (t2_final, account_id, latest_version))
            conn.commit()
            conn.close()

        timeline.append(tx2.record_step("T2", "RETRY_UPDATE", res_key, f"Re-read balance=${latest_balance:.2f}, version={latest_version}. Updated to ${t2_final:.2f}, version={latest_version + 1}", "SUCCESS"))
        self.tx_mgr.commit(tx2.tx_id, thread_tag="T2")
        timeline.append(tx2.record_step("T2", "COMMIT", res_key, "Committed successfully on retry", "COMMITTED"))

        record_conflict(
            transaction_id=tx2.tx_id,
            conflict_type="LOST_UPDATE",
            severity="LOW",
            resolution_status="PREVENTED_OPTIMISTIC",
            details={
                "mode": "optimistic",
                "final_balance": t2_final,
                "data_loss": 0.00,
                "message": "Optimistic lock detected version mismatch and retried cleanly without lost update."
            }
        )
        log_audit("OPTIMISTIC_LOCK_ENFORCED", "SUCCESS", user_id=user_id, payload_summary=f"Optimistic retry succeeded. Final balance: ${t2_final:.2f}")

        return {
            "mode": "optimistic",
            "success": True,
            "anomaly_detected": False,
            "final_balance": t2_final,
            "data_loss": 0.00,
            "message": f"SUCCESS: Optimistic concurrency control detected conflict and serialized update cleanly. Final balance: ${t2_final:.2f}."
        }

    def _simulate_atomic_lost_update(self, account_id, initial_balance, deduct_t1, deduct_t2, user_id, timeline):
        tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Atomic SQL)", thread_tag="T1")
        tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Lost Update (Atomic SQL)", thread_tag="T2")
        res_key = f"demo_accounts:{account_id}"

        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("UPDATE demo_accounts SET balance = balance - ? WHERE account_id = ? AND balance >= ?;", (deduct_t1, account_id, deduct_t1))
            conn.commit()
            timeline.append(tx1.record_step("T1", "ATOMIC_UPDATE", res_key, f"SET balance = balance - {deduct_t1}", "SUCCESS"))

            cur.execute("UPDATE demo_accounts SET balance = balance - ? WHERE account_id = ? AND balance >= ?;", (deduct_t2, account_id, deduct_t2))
            conn.commit()
            timeline.append(tx2.record_step("T2", "ATOMIC_UPDATE", res_key, f"SET balance = balance - {deduct_t2}", "SUCCESS"))

            cur.execute("SELECT balance FROM demo_accounts WHERE account_id = ?;", (account_id,))
            final_balance = float(cur.fetchone()["balance"])
            conn.close()

        self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")
        self.tx_mgr.commit(tx2.tx_id, thread_tag="T2")

        return {
            "mode": "atomic",
            "success": True,
            "anomaly_detected": False,
            "final_balance": final_balance,
            "data_loss": 0.00,
            "message": f"SUCCESS: In-database atomic expressions serialized updates cleanly. Final balance: ${final_balance:.2f}."
        }

    # =========================================================================
    # 2. DOUBLE-BOOKING / DUPLICATE RESERVATION SCENARIO
    # =========================================================================
    def run_double_booking(self, mode="safe", ticket_id=1, user_id=1):
        """
        Simulates two concurrent users attempting to book the exact same seat.
        """
        timeline = []
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT ticket_id, seat_code, price, status FROM demo_tickets WHERE ticket_id = ?;", (ticket_id,))
            ticket = cur.fetchone()
            if not ticket:
                cur.execute("INSERT INTO demo_tickets (ticket_id, event_name, seat_code, price, status) VALUES (?, 'Tech Summit 2026', 'A-101', 150.00, 'AVAILABLE');")
                conn.commit()
                ticket = {"ticket_id": ticket_id, "seat_code": "A-101", "price": 150.0, "status": "AVAILABLE"}
            seat_code = ticket["seat_code"]
            conn.close()

        res_key = f"demo_tickets:{ticket_id}"

        if mode == "unsafe":
            tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Double Booking (Unsafe)", thread_tag="T1")
            tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Double Booking (Unsafe)", thread_tag="T2")

            timeline.append(tx1.record_step("T1", "CHECK_SEAT", res_key, f"Seat {seat_code} is AVAILABLE", "SUCCESS"))
            timeline.append(tx2.record_step("T2", "CHECK_SEAT", res_key, f"Seat {seat_code} is AVAILABLE (Race condition!)", "SUCCESS"))

            # T1 books seat
            with DB_LOCK:
                conn = get_sqlite_connection()
                conn.execute("UPDATE demo_tickets SET status = 'BOOKED', booked_by_user_id = 1 WHERE ticket_id = ?;", (ticket_id,))
                conn.execute("INSERT INTO demo_reservations (user_id, ticket_id, amount_paid, status) VALUES (1, ?, 150.00, 'CONFIRMED');", (ticket_id,))
                conn.commit()
                conn.close()

            timeline.append(tx1.record_step("T1", "RESERVE", res_key, "Confirmed reservation for User 1", "SUCCESS"))
            self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")

            # T2 also books seat without checking updated state!
            with DB_LOCK:
                conn = get_sqlite_connection()
                conn.execute("INSERT INTO demo_reservations (user_id, ticket_id, amount_paid, status) VALUES (2, ?, 150.00, 'CONFIRMED');", (ticket_id,))
                conn.commit()
                conn.close()

            timeline.append(tx2.record_step("T2", "RESERVE", res_key, "Confirmed reservation for User 2 (DOUBLE BOOKING ANOMALY!)", "WARNING"))
            self.tx_mgr.commit(tx2.tx_id, thread_tag="T2")

            record_conflict(
                transaction_id=tx2.tx_id,
                conflict_type="DOUBLE_BOOKING",
                severity="HIGH",
                resolution_status="DETECTED_CORRUPTED",
                details={"seat_code": seat_code, "message": f"Seat {seat_code} was double booked by User 1 and User 2!"}
            )
            log_audit("DOUBLE_BOOKING_ANOMALY", "FAILURE", user_id=user_id, payload_summary=f"Seat {seat_code} double booked.")

            return {
                "mode": "unsafe",
                "success": True,
                "conflict_detected": True,
                "message": f"CONFLICT DETECTED: Seat '{seat_code}' was double-booked by two concurrent transactions!",
                "timeline": timeline
            }

        else:
            # Safe Mode: Pessimistic Row Lock + Constraint validation
            tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Double Booking (Safe)", thread_tag="T1")
            tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Double Booking (Safe)", thread_tag="T2")

            # T1 acquires exclusive lock
            self.lock_mgr.acquire_lock(res_key, tx1.tx_id, mode="EXCLUSIVE")
            timeline.append(tx1.record_step("T1", "SELECT ... FOR UPDATE", res_key, "Acquired row lock on seat", "SUCCESS"))

            # T2 attempts lock -> enters wait
            timeline.append(tx2.record_step("T2", "SELECT ... FOR UPDATE", res_key, "Blocked waiting for seat lock", "LOCK_WAIT"))

            # T1 books
            with DB_LOCK:
                conn = get_sqlite_connection()
                conn.execute("UPDATE demo_tickets SET status = 'BOOKED', booked_by_user_id = 1 WHERE ticket_id = ?;", (ticket_id,))
                conn.execute("INSERT INTO demo_reservations (user_id, ticket_id, amount_paid, status) VALUES (1, ?, 150.00, 'CONFIRMED');", (ticket_id,))
                conn.commit()
                conn.close()

            timeline.append(tx1.record_step("T1", "BOOK", res_key, "Booked seat for User 1", "SUCCESS"))
            self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")
            timeline.append(tx1.record_step("T1", "COMMIT", res_key, "Committed. Lock released.", "COMMITTED"))

            # T2 acquires lock, inspects status
            self.lock_mgr.acquire_lock(res_key, tx2.tx_id, mode="EXCLUSIVE")
            timeline.append(tx2.record_step("T2", "LOCK_ACQUIRED", res_key, "Lock acquired after T1 release", "SUCCESS"))

            try:
                IntegrityValidator.validate_seat_availability(seat_code, "BOOKED", user_id=user_id)
            except IntegrityViolationException as ive:
                timeline.append(tx2.record_step("T2", "INTEGRITY_CHECK", res_key, ive.details["message"], "ERROR"))
                self.tx_mgr.rollback(tx2.tx_id, thread_tag="T2", reason=ive.details["message"])
                timeline.append(tx2.record_step("T2", "ROLLBACK", res_key, "Transaction rolled back cleanly without double-booking", "ROLLED_BACK"))

            record_conflict(
                transaction_id=tx2.tx_id,
                conflict_type="DOUBLE_BOOKING",
                severity="MEDIUM",
                resolution_status="PREVENTED_PESSIMISTIC",
                details={"seat_code": seat_code, "message": "Pessimistic lock and constraint check prevented double booking."}
            )

            return {
                "mode": "safe",
                "success": True,
                "conflict_detected": False,
                "message": f"SUCCESS: Double booking prevented! Seat '{seat_code}' was locked and protected from concurrent overwrite.",
                "timeline": timeline
            }

    # =========================================================================
    # 3. DEADLOCK SIMULATION & CONTROLLED AUTO-RETRY
    # =========================================================================
    def run_deadlock(self, mode="auto_retry", user_id=1):
        """
        Simulates cross-locking deadlock between T1 and T2:
        T1 locks Account A, requests Account B.
        T2 locks Account B, requests Account A.
        Wait-For Graph cycle -> MySQL Error 1213.
        In 'auto_retry' mode, the victim transaction is caught, rolled back,
        and retried with backoff until both successfully commit.
        """
        timeline = []
        res_a = "demo_accounts:1"
        res_b = "demo_accounts:2"

        # Ensure both locks are clean
        self.lock_mgr.reset()

        tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Deadlock Simulation", thread_tag="T1")
        tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Deadlock Simulation", thread_tag="T2")

        # Step 1: T1 acquires lock on Resource A
        self.lock_mgr.acquire_lock(res_a, tx1.tx_id, mode="EXCLUSIVE")
        timeline.append(tx1.record_step("T1", "LOCK", res_a, "Acquired exclusive lock on Account 1", "SUCCESS"))

        # Step 2: T2 acquires lock on Resource B
        self.lock_mgr.acquire_lock(res_b, tx2.tx_id, mode="EXCLUSIVE")
        timeline.append(tx2.record_step("T2", "LOCK", res_b, "Acquired exclusive lock on Account 2", "SUCCESS"))

        # Step 3: T1 requests Resource B (held by T2) -> T1 waits
        timeline.append(tx1.record_step("T1", "REQUEST_LOCK", res_b, "Requesting lock on Account 2 (Held by T2) -> Waiting", "LOCK_WAIT"))
        with self.lock_mgr.mutex:
            self.lock_mgr.wait_for_graph[tx1.tx_id].add(tx2.tx_id)

        # Step 4: T2 requests Resource A (held by T1) -> Wait-For Graph cycle!
        timeline.append(tx2.record_step("T2", "REQUEST_LOCK", res_a, "Requesting lock on Account 1 (Held by T1) -> CYCLE DETECTED!", "DEADLOCK"))

        deadlock_cycle = None
        deadlock_err = None
        try:
            self.lock_mgr.acquire_lock(res_a, tx2.tx_id, mode="EXCLUSIVE")
        except DeadlockException as e:
            deadlock_err = e
            deadlock_cycle = e.cycle

        timeline.append(tx2.record_step("T2", "ERROR_1213", "SYSTEM", f"MySQL Error 1213: Deadlock found when trying to get lock. Cycle: {' -> '.join(deadlock_cycle or ['T1', 'T2', 'T1'])}", "DEADLOCK_ABORTED"))

        if mode == "unsafe_deadlock":
            # Abort T2 without retry
            self.tx_mgr.rollback(tx2.tx_id, thread_tag="T2", deadlock=True, reason="Deadlock cycle detected (unhandled)")
            # T1 finishes
            self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")
            record_conflict(
                transaction_id=tx2.tx_id,
                conflict_type="DEADLOCK",
                severity="CRITICAL",
                resolution_status="ROLLED_BACK",
                details={"cycle": deadlock_cycle, "message": "Deadlock cycle aborted transaction without retry."}
            )
            return {
                "mode": "unsafe_deadlock",
                "success": False,
                "deadlock_detected": True,
                "cycle": deadlock_cycle,
                "message": "DEADLOCK ENCOUNTERED: MySQL Error 1213. Transaction T2 was aborted.",
                "timeline": timeline
            }

        else:
            # Auto-Retry Mode: Controlled recovery with exponential backoff
            timeline.append(tx2.record_step("T2", "AUTO_RECOVERY", "RETRY_HANDLER", "Deadlock caught by DBGuard. Rolling back victim transaction T2 and scheduling retry...", "RUNNING"))
            self.tx_mgr.rollback(tx2.tx_id, thread_tag="T2", deadlock=True, reason="Deadlock auto-recovery victim rollback")

            # T1 can now proceed and complete
            timeline.append(tx1.record_step("T1", "RESUME", res_b, "Acquired lock on Account 2 now that T2 released it", "SUCCESS"))
            self.tx_mgr.commit(tx1.tx_id, thread_tag="T1")
            timeline.append(tx1.record_step("T1", "COMMIT", "demo_accounts", "Transaction T1 successfully committed", "COMMITTED"))

            # Retry T2 with backoff
            time.sleep(0.05)  # Simulated exponential backoff (50ms)
            tx2_retry = self.tx_mgr.begin(user_id=user_id, scenario_name="Deadlock Simulation (Retry)", thread_tag="T2-Retry")
            timeline.append(tx2_retry.record_step("T2-Retry", "RESTART_TRANSACTION", "SYSTEM", "Retrying transaction with backoff...", "RUNNING"))

            self.lock_mgr.acquire_lock(res_b, tx2_retry.tx_id, mode="EXCLUSIVE")
            timeline.append(tx2_retry.record_step("T2-Retry", "LOCK", res_b, "Acquired lock on Account 2", "SUCCESS"))

            self.lock_mgr.acquire_lock(res_a, tx2_retry.tx_id, mode="EXCLUSIVE")
            timeline.append(tx2_retry.record_step("T2-Retry", "LOCK", res_a, "Acquired lock on Account 1", "SUCCESS"))

            self.tx_mgr.commit(tx2_retry.tx_id, thread_tag="T2-Retry")
            timeline.append(tx2_retry.record_step("T2-Retry", "COMMIT", "demo_accounts", "Transaction T2 committed successfully on retry attempt #1", "COMMITTED"))

            record_conflict(
                transaction_id=tx2.tx_id,
                conflict_type="DEADLOCK",
                severity="CRITICAL",
                resolution_status="RETRIED_SUCCESSFULLY",
                details={
                    "cycle": deadlock_cycle,
                    "retries": 1,
                    "backoff_ms": 50,
                    "message": "Deadlock cycle (Error 1213) resolved automatically via backoff retry."
                }
            )
            log_audit("DEADLOCK_AUTO_RECOVERED", "SUCCESS", user_id=user_id, payload_summary="Deadlock cycle auto-recovered with zero human intervention.")

            return {
                "mode": "auto_retry",
                "success": True,
                "deadlock_detected": True,
                "retried_successfully": True,
                "cycle": deadlock_cycle,
                "message": "DEADLOCK DETECTED & RESOLVED: Cycle caught (MySQL Error 1213). Auto-retry handler restarted victim transaction with backoff, completing both transactions successfully!",
                "timeline": timeline
            }

    # =========================================================================
    # 4. DIRTY READ SIMULATION & PREVENTED VIA READ COMMITTED
    # =========================================================================
    def run_dirty_read(self, mode="unsafe", account_id=1, user_id=1):
        """
        Simulates Dirty Read anomaly (A1):
        T1 updates balance to $0.00.
        T2 reads uncommitted $0.00.
        T1 aborts/rolls back.
        In 'unsafe' mode: T2 acted on dirty rolled-back value!
        In 'safe' mode: Read Committed snapshot prevents reading uncommitted data.
        """
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT balance FROM demo_accounts WHERE account_id = ?;", (account_id,))
            row = cur.fetchone()
            initial_balance = float(row["balance"]) if row else 1000.00
            conn.close()

        timeline = []
        res_key = f"demo_accounts:{account_id}"
        tx1 = self.tx_mgr.begin(user_id=user_id, scenario_name="Dirty Read (T1)", thread_tag="T1")
        tx2 = self.tx_mgr.begin(user_id=user_id, scenario_name="Dirty Read (T2)", thread_tag="T2")

        dirty_val = 0.00
        timeline.append(tx1.record_step("T1", "UPDATE (UNCOMMITTED)", res_key, f"T1 modified balance from ${initial_balance:.2f} to ${dirty_val:.2f} (Uncommitted)", "WARNING"))

        if mode == "unsafe":
            t2_observed = dirty_val
            timeline.append(tx2.record_step("T2", "READ_UNCOMMITTED", res_key, f"T2 read dirty uncommitted balance = ${t2_observed:.2f}!", "WARNING"))
            
            self.tx_mgr.rollback(tx1.tx_id, thread_tag="T1", reason="Transaction error: rolling back uncommitted writes")
            timeline.append(tx1.record_step("T1", "ROLLBACK", res_key, f"T1 aborted and rolled back. Balance restored to ${initial_balance:.2f}", "ROLLED_BACK"))

            self.tx_mgr.commit(tx2.tx_id, thread_tag="T2")
            timeline.append(tx2.record_step("T2", "COMMIT", res_key, f"T2 committed decision based on phantom uncommitted value ${t2_observed:.2f}!", "COMMITTED"))

            return {
                "mode": "unsafe",
                "success": False,
                "anomaly_detected": True,
                "initial_balance": initial_balance,
                "t2_observed": t2_observed,
                "final_balance": initial_balance,
                "message": f"ANOMALY TRIGGERED: Dirty Read! T2 observed uncommitted ${t2_observed:.2f} before T1 rolled back.",
                "timeline": timeline
            }
        else:
            t2_observed = initial_balance
            timeline.append(tx2.record_step("T2", "READ_COMMITTED", res_key, f"Read Committed MVCC snapshot isolated T2. Read confirmed balance = ${t2_observed:.2f}", "SUCCESS"))

            self.tx_mgr.rollback(tx1.tx_id, thread_tag="T1", reason="Transaction error: rolling back")
            timeline.append(tx1.record_step("T1", "ROLLBACK", res_key, f"T1 rolled back cleanly. Uncommitted write erased.", "ROLLED_BACK"))

            self.tx_mgr.commit(tx2.tx_id, thread_tag="T2")
            timeline.append(tx2.record_step("T2", "COMMIT", res_key, f"T2 committed safely with verified committed state ${t2_observed:.2f}.", "COMMITTED"))

            return {
                "mode": "safe",
                "success": True,
                "anomaly_detected": False,
                "initial_balance": initial_balance,
                "t2_observed": t2_observed,
                "final_balance": initial_balance,
                "message": f"SUCCESS: Dirty Read prevented! Read Committed MVCC snapshot shielded T2 from uncommitted data.",
                "timeline": timeline
            }

    # =========================================================================
    # 4. SAVEPOINT & PARTIAL ROLLBACK SCENARIO
    # =========================================================================
    def run_savepoint_scenario(self, user_id=1):
        return RecoveryManager.run_savepoint_batch_demo(user_id=user_id)

    # =========================================================================
    # 5. INTEGRITY CONSTRAINT VIOLATION SCENARIO
    # =========================================================================
    def run_integrity_violation_scenario(self, account_id=1, deduct_amount=1500.0, user_id=1):
        """
        Attempts to deduct $1,500 from Account 1 (balance $700.00).
        Violates CHECK constraint (balance >= 0.00) -> MySQL Error 3819.
        Logs violation and ensures zero partial corruption occurs.
        """
        timeline = []
        with DB_LOCK:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT balance FROM demo_accounts WHERE account_id = ?;", (account_id,))
            current_balance = float(cur.fetchone()["balance"])
            conn.close()

        tx = self.tx_mgr.begin(user_id=user_id, scenario_name="Integrity Constraint Check", thread_tag="T1")
        timeline.append(tx.record_step("T1", "READ_BALANCE", f"demo_accounts:{account_id}", f"Current balance: ${current_balance:.2f}", "SUCCESS"))

        attempted_balance = current_balance - deduct_amount
        timeline.append(tx.record_step("T1", "ATTEMPT_DEDUCT", f"demo_accounts:{account_id}", f"Attempting deduction of ${deduct_amount:.2f} (New balance: ${attempted_balance:.2f})", "RUNNING"))

        try:
            IntegrityValidator.validate_positive_balance(attempted_balance, account_number=f"ACC-{account_id:04d}", user_id=user_id)
        except IntegrityViolationException as ive:
            timeline.append(tx.record_step("T1", "CHECK_CONSTRAINT_FAILED", f"demo_accounts:{account_id}", ive.details["mysql_error"], "ERROR"))
            self.tx_mgr.rollback(tx.tx_id, thread_tag="T1", reason=ive.details["message"])
            timeline.append(tx.record_step("T1", "ROLLBACK", f"demo_accounts:{account_id}", "Transaction aborted cleanly. No balance changes saved.", "ROLLED_BACK"))

            return {
                "success": False,
                "violation_blocked": True,
                "error_code": 3819,
                "mysql_error": ive.details["mysql_error"],
                "message": f"INTEGRITY VIOLATION BLOCKED: {ive.details['message']} Zero partial state saved.",
                "timeline": timeline
            }

        return {"success": True, "timeline": timeline}
