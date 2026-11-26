"""
DBGuard Integrity Validator Engine
Validates domain invariants and intercepts MySQL/database constraint violations:
- MySQL 3819: CHECK constraint failed (e.g. balance >= 0.00)
- MySQL 1062: Duplicate entry for key (PRIMARY/UNIQUE)
- MySQL 1452: Cannot add or update a child row: a foreign key constraint fails
"""

from db.database import record_integrity_violation, log_audit

class IntegrityViolationException(Exception):
    def __init__(self, constraint_type, table_name, details, error_code=None):
        self.constraint_type = constraint_type
        self.table_name = table_name
        self.details = details
        self.error_code = error_code or 3819
        super().__init__(f"Integrity Violation [{constraint_type}] on table '{table_name}': {details.get('message', '')}")

class IntegrityValidator:
    @staticmethod
    def validate_positive_balance(balance, account_number="N/A", user_id=None):
        """Enforces positive balance constraint (chk_positive_balance: balance >= 0.00)."""
        if balance < 0:
            details = {
                "constraint": "chk_positive_balance",
                "attempted_balance": balance,
                "account_number": account_number,
                "message": f"Check constraint failed: balance ${balance:.2f} is strictly below zero minimum allowed ($0.00).",
                "mysql_error": "Error 3819 (HY000): Check constraint 'chk_positive_balance' is violated."
            }
            record_integrity_violation(
                resource_id=1,  # demo_accounts
                constraint_type="CHECK_CONSTRAINT",
                table_name="demo_accounts",
                details=details
            )
            log_audit("INTEGRITY_CHECK_FAILED", "FAILURE", user_id, payload_summary=details["message"])
            raise IntegrityViolationException("CHECK_CONSTRAINT", "demo_accounts", details, error_code=3819)
        return True

    @staticmethod
    def validate_seat_availability(seat_code, current_status, user_id=None):
        """Validates that a seat can only be booked if currently AVAILABLE."""
        if current_status != "AVAILABLE":
            details = {
                "constraint": "seat_unique_reservation",
                "seat_code": seat_code,
                "current_status": current_status,
                "message": f"Seat '{seat_code}' is currently '{current_status}' and cannot be reserved again.",
                "mysql_error": "Error 1062 (23000): Duplicate entry for key 'demo_tickets.seat_code'."
            }
            record_integrity_violation(
                resource_id=2,  # demo_tickets
                constraint_type="UNIQUE",
                table_name="demo_tickets",
                details=details
            )
            log_audit("DOUBLE_BOOKING_PREVENTED", "FAILURE", user_id, payload_summary=details["message"])
            raise IntegrityViolationException("UNIQUE", "demo_tickets", details, error_code=1062)
        return True

    @staticmethod
    def validate_foreign_key_user(user_id):
        """Validates that a user exists for foreign key references."""
        from db.database import get_sqlite_connection
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM dbguard_users WHERE user_id = ?;", (user_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            details = {
                "constraint": "fk_booked_user",
                "user_id": user_id,
                "message": f"Foreign Key violation: User ID {user_id} does not exist in 'dbguard_users'.",
                "mysql_error": "Error 1452 (23000): Cannot add child row: foreign key constraint fails."
            }
            record_integrity_violation(
                resource_id=2,
                constraint_type="FOREIGN_KEY",
                table_name="demo_tickets",
                details=details
            )
            raise IntegrityViolationException("FOREIGN_KEY", "demo_tickets", details, error_code=1452)
        return True
