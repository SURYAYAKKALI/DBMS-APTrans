"""
Business Invariant Verification Engine
Validates critical real-world business constraints such as non-negative stock,
exclusive equipment reservations, and active duty minimums.
"""

from typing import List, Dict, Any
from database.connection import db_manager
from business_app.inventory.service import InventoryService
from business_app.reservations.service import ReservationService

class InvariantEngine:
    @staticmethod
    def validate_all_invariants(run_id: str) -> List[Dict[str, Any]]:
        violations = []
        conn = db_manager.get_raw_connection()
        cursor = conn.cursor()

        try:
            # 1. Invariant: Inventory Quantity Non-Negative
            cursor.execute("SELECT inventory_id, equipment_id, quantity FROM inventory WHERE quantity < 0")
            neg_rows = cursor.fetchall()
            for r in neg_rows:
                violations.append({
                    "rule_id": "RULE-NON-NEGATIVE-STOCK",
                    "rule_name": "Inventory Quantity Non-Negative",
                    "severity": "CRITICAL",
                    "target_table": "inventory",
                    "violation_details": f"Inventory {r[0]} (Equipment {r[1]}) has negative stock: {r[2]}! Indicates overselling.",
                    "status": "VIOLATED"
                })

            # 2. Invariant: At Least One Doctor On Duty (Write Skew invariant)
            cursor.execute("SELECT COUNT(*) FROM doctors WHERE shift_date = '2026-11-02' AND on_duty = 1")
            duty_count = cursor.fetchone()[0]
            if duty_count < 1:
                violations.append({
                    "rule_id": "RULE-AT-LEAST-ONE-ON-DUTY",
                    "rule_name": "At Least One Doctor On Duty",
                    "severity": "CRITICAL",
                    "target_table": "doctors",
                    "violation_details": f"Active duty count is {duty_count}! Hospital left without any attending doctor on duty due to concurrent write skew.",
                    "status": "VIOLATED"
                })

            # 3. Invariant: No Overlapping Confirmed Reservations
            cursor.execute("""
                SELECT r1.reservation_id, r2.reservation_id, r1.equipment_id, r1.start_time, r1.end_time
                FROM reservations r1
                JOIN reservations r2 ON r1.equipment_id = r2.equipment_id 
                    AND r1.reservation_id < r2.reservation_id
                    AND r1.status = 'CONFIRMED' AND r2.status = 'CONFIRMED'
                    AND NOT (r1.end_time <= r2.start_time OR r1.start_time >= r2.end_time)
            """)
            overlaps = cursor.fetchall()
            for r in overlaps:
                violations.append({
                    "rule_id": "RULE-NO-OVERLAPPING-RESERVATIONS",
                    "rule_name": "Exclusive Equipment Reservation",
                    "severity": "CRITICAL",
                    "target_table": "reservations",
                    "violation_details": f"Double booking detected! Reservations {r[0]} and {r[1]} overlap for equipment {r[2]}.",
                    "status": "VIOLATED"
                })

        finally:
            conn.close()

        return violations

invariant_engine = InvariantEngine()
