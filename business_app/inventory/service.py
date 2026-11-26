"""
Inventory Business Service
Supports both vulnerable read-modify-write patterns and corrected patterns
(Atomic update, Optimistic Concurrency Control, and Pessimistic Locking).
"""

import sqlite3
from typing import Optional, Dict, Any, Tuple

class InventoryService:
    @staticmethod
    def get_stock(conn, equipment_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute("SELECT inventory_id, equipment_id, quantity, version FROM inventory WHERE equipment_id = ?", (equipment_id,))
        row = cursor.fetchone()
        if row:
            if isinstance(row, sqlite3.Row):
                return dict(row)
            return {"inventory_id": row[0], "equipment_id": row[1], "quantity": row[2], "version": row[3]}
        return None

    @staticmethod
    def vulnerable_stock_deduct(conn, equipment_id: str, deduct_qty: int = 1) -> Tuple[bool, int, int, str]:
        """
        Vulnerable application-level Read-Modify-Write pattern:
        1. Read stock into application memory
        2. Check if stock >= deduct_qty
        3. Write back new_qty = current - deduct_qty without atomic guard or version check.
        Subject to Lost Update anomalies under Read Committed!
        """
        cursor = conn.cursor()
        cursor.execute("SELECT quantity, version FROM inventory WHERE equipment_id = ?", (equipment_id,))
        row = cursor.fetchone()
        if not row:
            return False, 0, 0, "Item not found"
        
        current_qty = row[0]
        current_ver = row[1]
        
        if current_qty < deduct_qty:
            return False, current_qty, current_qty, "Insufficient inventory"

        # Simulating business processing delay between read and write
        new_qty = current_qty - deduct_qty
        cursor.execute("UPDATE inventory SET quantity = ?, last_updated = CURRENT_TIMESTAMP WHERE equipment_id = ?", (new_qty, equipment_id))
        return True, current_qty, new_qty, "Success"

    @staticmethod
    def corrected_atomic_deduct(conn, equipment_id: str, deduct_qty: int = 1) -> Tuple[bool, int, int, str]:
        """
        Corrective Strategy 1: Database-level Atomic Guard
        UPDATE inventory SET quantity = quantity - ? WHERE equipment_id = ? AND quantity >= ?
        """
        cursor = conn.cursor()
        cursor.execute("SELECT quantity, version FROM inventory WHERE equipment_id = ?", (equipment_id,))
        row = cursor.fetchone()
        old_qty = row[0] if row else 0

        cursor.execute(
            "UPDATE inventory SET quantity = quantity - ?, last_updated = CURRENT_TIMESTAMP "
            "WHERE equipment_id = ? AND quantity >= ?",
            (deduct_qty, equipment_id, deduct_qty)
        )
        if cursor.rowcount > 0:
            cursor.execute("SELECT quantity FROM inventory WHERE equipment_id = ?", (equipment_id,))
            new_qty = cursor.fetchone()[0]
            return True, old_qty, new_qty, "Atomic deduction succeeded"
        else:
            return False, old_qty, old_qty, "Deduction rejected: insufficient stock"

    @staticmethod
    def corrected_occ_deduct(conn, equipment_id: str, deduct_qty: int = 1, expected_version: int = 1) -> Tuple[bool, int, int, str]:
        """
        Corrective Strategy 2: Optimistic Concurrency Control (OCC)
        UPDATE inventory SET quantity = ?, version = version + 1 WHERE equipment_id = ? AND version = ?
        """
        cursor = conn.cursor()
        cursor.execute("SELECT quantity, version FROM inventory WHERE equipment_id = ?", (equipment_id,))
        row = cursor.fetchone()
        if not row:
            return False, 0, 0, "Item not found"

        current_qty = row[0]
        current_ver = row[1]

        if current_qty < deduct_qty:
            return False, current_qty, current_qty, "Insufficient stock"

        new_qty = current_qty - deduct_qty
        cursor.execute(
            "UPDATE inventory SET quantity = ?, version = version + 1, last_updated = CURRENT_TIMESTAMP "
            "WHERE equipment_id = ? AND version = ?",
            (new_qty, equipment_id, expected_version)
        )
        if cursor.rowcount > 0:
            return True, current_qty, new_qty, "OCC deduction succeeded"
        else:
            return False, current_qty, current_qty, "OCC conflict detected: version mismatch"

    @staticmethod
    def reset_inventory(conn, equipment_id: str = "EQ-LAPTOP-01", initial_quantity: int = 1):
        cursor = conn.cursor()
        cursor.execute("UPDATE inventory SET quantity = ?, version = 1 WHERE equipment_id = ?", (initial_quantity, equipment_id))
        cursor.execute("UPDATE equipment SET available_quantity = ? WHERE equipment_id = ?", (initial_quantity, equipment_id))
        conn.commit()
