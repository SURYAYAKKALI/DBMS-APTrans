"""
Reservation Business Service
Supports checking reservation overlaps, creating reservations, and doctor duty skew testing.
"""

import sqlite3
import datetime
from typing import Optional, Dict, Any, List, Tuple

class ReservationService:
    @staticmethod
    def get_overlapping_reservations(conn, equipment_id: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reservation_id, user_id, equipment_id, start_time, end_time, status "
            "FROM reservations "
            "WHERE equipment_id = ? AND status = 'CONFIRMED' "
            "AND NOT (end_time <= ? OR start_time >= ?)",
            (equipment_id, start_time, end_time)
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            if isinstance(r, sqlite3.Row):
                results.append(dict(r))
            else:
                results.append({
                    "reservation_id": r[0],
                    "user_id": r[1],
                    "equipment_id": r[2],
                    "start_time": r[3],
                    "end_time": r[4],
                    "status": r[5]
                })
        return results

    @staticmethod
    def vulnerable_reserve(conn, res_id: str, user_id: str, equipment_id: str, start_time: str, end_time: str) -> Tuple[bool, str]:
        """
        Vulnerable reservation flow without predicate lock:
        1. Check overlapping bookings
        2. If none, insert reservation
        Under Read Committed / Repeatable Read, two concurrent transactions can both pass check and insert overlapping bookings (Write Skew / Phantom)!
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM reservations "
            "WHERE equipment_id = ? AND status = 'CONFIRMED' "
            "AND NOT (end_time <= ? OR start_time >= ?)",
            (equipment_id, start_time, end_time)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            return False, "Conflict: time slot already reserved"

        cursor.execute(
            "INSERT INTO reservations (reservation_id, user_id, equipment_id, start_time, end_time, status) "
            "VALUES (?, ?, ?, ?, ?, 'CONFIRMED')",
            (res_id, user_id, equipment_id, start_time, end_time)
        )
        return True, "Reservation confirmed"

    @staticmethod
    def get_doctors_on_duty(conn, shift_date: str = "2026-11-02") -> int:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM doctors WHERE shift_date = ? AND on_duty = 1", (shift_date,))
        row = cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    def vulnerable_doctor_leave(conn, doctor_id: str, shift_date: str = "2026-11-02") -> Tuple[bool, str]:
        """
        Canonical Write Skew pattern (Jim Gray / Alan Fekete / Adya):
        Invariant: At least 1 doctor must be on duty.
        Txn 1 reads on_duty count (=2).
        Txn 2 reads on_duty count (=2).
        Txn 1 updates Doc1 on_duty = 0.
        Txn 2 updates Doc2 on_duty = 0.
        Both commit! On duty count becomes 0, violating the invariant!
        """
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM doctors WHERE shift_date = ? AND on_duty = 1", (shift_date,))
        count = cursor.fetchone()[0]
        if count < 2:
            return False, "Cannot leave: at least one doctor must remain on duty"

        cursor.execute("UPDATE doctors SET on_duty = 0 WHERE doctor_id = ? AND shift_date = ?", (doctor_id, shift_date))
        return True, f"Doctor {doctor_id} taken off duty"

    @staticmethod
    def corrected_doctor_leave_serializable(conn, doctor_id: str, shift_date: str = "2026-11-02") -> Tuple[bool, str]:
        """
        Corrective Strategy for Write Skew:
        Requires Serializable isolation or explicit table lock / predicate lock.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM doctors WHERE shift_date = ? AND on_duty = 1", (shift_date,))
        count = cursor.fetchone()[0]
        if count < 2:
            return False, "Cannot leave: minimum duty constraint"

        cursor.execute("UPDATE doctors SET on_duty = 0 WHERE doctor_id = ? AND shift_date = ?", (doctor_id, shift_date))
        return True, f"Doctor {doctor_id} taken off duty"

    @staticmethod
    def reset_doctors(conn):
        cursor = conn.cursor()
        cursor.execute("UPDATE doctors SET on_duty = 1 WHERE shift_date = '2026-11-02'")
        conn.commit()
