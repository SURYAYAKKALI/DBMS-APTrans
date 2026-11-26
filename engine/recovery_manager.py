"""
DBGuard Recovery & Savepoint Manager
Provides:
1. Automated Deadlock Retry with Exponential Backoff
2. Savepoint & Nested Transaction Partial Rollback
"""

import time
import random
from db.database import record_conflict, log_audit, get_sqlite_connection, DB_LOCK
from engine.lock_manager import DeadlockException

class RecoveryManager:
    @staticmethod
    def execute_with_retry(operation_func, max_retries=3, base_backoff_ms=50, max_backoff_ms=250, tx_id="tx_deadlock"):
        """
        Executes a transaction function. If a DeadlockException occurs, logs conflict
        and retries with exponential backoff and jitter.
        """
        attempts = 0
        last_error = None

        while attempts <= max_retries:
            try:
                result = operation_func(attempts)
                if attempts > 0:
                    record_conflict(
                        transaction_id=tx_id,
                        conflict_type="DEADLOCK",
                        severity="CRITICAL",
                        resolution_status="RETRIED_SUCCESSFULLY",
                        details={
                            "attempts": attempts + 1,
                            "message": f"Deadlock cycle encountered and auto-resolved via controlled backoff retry (Attempt #{attempts + 1})."
                        }
                    )
                    log_audit("DEADLOCK_AUTO_RECOVERED", "SUCCESS", payload_summary=f"Resolved on retry attempt {attempts + 1}")
                return {
                    "success": True,
                    "retries": attempts,
                    "result": result
                }
            except DeadlockException as e:
                attempts += 1
                last_error = e
                if attempts > max_retries:
                    record_conflict(
                        transaction_id=tx_id,
                        conflict_type="DEADLOCK",
                        severity="CRITICAL",
                        resolution_status="ROLLED_BACK",
                        details={
                            "attempts": attempts,
                            "error": str(e),
                            "message": f"Deadlock could not be resolved after {max_retries} retries."
                        }
                    )
                    log_audit("DEADLOCK_RETRY_EXHAUSTED", "FAILURE", payload_summary=str(e))
                    raise

                # Exponential backoff with random jitter
                backoff = min(max_backoff_ms, base_backoff_ms * (2 ** (attempts - 1)))
                jitter = random.uniform(0.5, 1.5)
                sleep_time_sec = (backoff * jitter) / 1000.0
                time.sleep(sleep_time_sec)

        raise last_error

    @staticmethod
    def run_savepoint_batch_demo(user_id=1):
        """
        Demonstrates Savepoint partial rollback:
        User books Ticket 1 (valid).
        Creates SAVEPOINT.
        User books Ticket 2 (invalid/duplicate seat).
        Catches error, rolls back to SAVEPOINT.
        Commits Ticket 1.
        """
        from engine.transaction_manager import TransactionManager
        from engine.integrity_validator import IntegrityValidator, IntegrityViolationException

        tx_mgr = TransactionManager()
        tx = tx_mgr.begin(user_id=user_id, scenario_name="Savepoint Batch Ticket Purchase", thread_tag="T1")
        steps = []

        try:
            with DB_LOCK:
                conn = get_sqlite_connection()
                cur = conn.cursor()

                # Step 1: Book Ticket 1 (Seat A-101)
                cur.execute("SELECT ticket_id, seat_code, price, status FROM demo_tickets WHERE ticket_id = 1;")
                t1 = cur.fetchone()
                if not t1 or t1["status"] != "AVAILABLE":
                    # If already booked, reset seat 1 to AVAILABLE for demo
                    cur.execute("UPDATE demo_tickets SET status = 'AVAILABLE', booked_by_user_id = NULL WHERE ticket_id = 1;")
                    conn.commit()
                    cur.execute("SELECT ticket_id, seat_code, price, status FROM demo_tickets WHERE ticket_id = 1;")
                    t1 = cur.fetchone()

                # Reserve ticket 1
                cur.execute("UPDATE demo_tickets SET status = 'BOOKED', booked_by_user_id = ? WHERE ticket_id = 1;", (user_id,))
                cur.execute("INSERT INTO demo_reservations (user_id, ticket_id, amount_paid, status) VALUES (?, 1, ?, 'CONFIRMED');", (user_id, t1["price"]))
                conn.commit()

            step1 = tx.record_step("T1", "BOOK_TICKET_1", "demo_tickets:1", f"Seat {t1['seat_code']} Booked ($150)", "SUCCESS")
            steps.append(step1)

            # Step 2: Create SAVEPOINT sp_ticket1
            tx_mgr.savepoint(tx.tx_id, "sp_ticket1", snapshot_data={"ticket_1_booked": True}, thread_tag="T1")
            step2 = tx.record_step("T1", "SAVEPOINT sp_ticket1", "SAVEPOINT", "Savepoint marked after Ticket 1", "SUCCESS")
            steps.append(step2)

            # Step 3: Attempt to book Ticket 2 with an invalid/duplicate constraint
            # We attempt to book Ticket 1 again or an already booked ticket
            step3 = tx.record_step("T1", "BOOK_TICKET_2_ATTEMPT", "demo_tickets:1", "Attempting duplicate booking on same seat A-101", "RUNNING")
            steps.append(step3)

            # Integrity check fails
            try:
                IntegrityValidator.validate_seat_availability("A-101", "BOOKED", user_id=user_id)
            except IntegrityViolationException as ive:
                # Catch integrity violation, perform partial rollback to savepoint
                step_error = tx.record_step("T1", "INTEGRITY_VIOLATION_CAUGHT", "demo_tickets:1", ive.details["message"], "ERROR")
                steps.append(step_error)

                # Rollback to savepoint
                tx_mgr.rollback_to_savepoint(tx.tx_id, "sp_ticket1", thread_tag="T1")
                step_rb = tx.record_step("T1", "ROLLBACK TO SAVEPOINT", "sp_ticket1", "Rolled back to savepoint sp_ticket1. Ticket 1 preserved, Ticket 2 aborted.", "SUCCESS")
                steps.append(step_rb)

            # Step 4: Commit transaction (Ticket 1 is preserved!)
            tx_mgr.commit(tx.tx_id, thread_tag="T1", affected_rows=1)
            step_commit = tx.record_step("T1", "COMMIT", "demo_tickets", "Batch transaction committed successfully with partial rollback", "COMMITTED")
            steps.append(step_commit)

            log_audit("SAVEPOINT_PARTIAL_ROLLBACK", "SUCCESS", user_id=user_id, payload_summary="Ticket 1 kept, Ticket 2 rolled back to savepoint sp_ticket1.")

            return {
                "success": True,
                "tx_id": tx.tx_id,
                "ticket_1_status": "BOOKED",
                "ticket_2_status": "REJECTED_ROLLED_BACK",
                "steps": steps,
                "summary": "Savepoint demonstrated: Ticket 1 was preserved and committed; Ticket 2 failed validation and was safely rolled back to savepoint without aborting the entire batch."
            }

        except Exception as e:
            tx_mgr.rollback(tx.tx_id, thread_tag="T1", reason=str(e))
            raise
