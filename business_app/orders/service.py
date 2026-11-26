"""
Order and Payment Services for Business Application
"""

import sqlite3
from typing import Dict, Any, Tuple

class OrderService:
    @staticmethod
    def create_order(conn, order_id: str, user_id: str, equipment_id: str, quantity: int, unit_price: float = 1200.0) -> Tuple[bool, str]:
        cursor = conn.cursor()
        total = quantity * unit_price
        cursor.execute(
            "INSERT INTO orders (order_id, user_id, equipment_id, quantity, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, 'PENDING')",
            (order_id, user_id, equipment_id, quantity, total)
        )
        return True, "Order created"

class PaymentService:
    @staticmethod
    def record_payment(conn, payment_id: str, order_id: str, amount: float) -> Tuple[bool, str]:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO payments (payment_id, order_id, amount, status) "
            "VALUES (?, ?, ?, 'COMPLETED')",
            (payment_id, order_id, amount)
        )
        cursor.execute("UPDATE orders SET status = 'PAID' WHERE order_id = ?", (order_id,))
        return True, "Payment recorded"
