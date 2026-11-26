"""
DBGuard System State, Metrics, Rules & Admin Reset Endpoints
"""

import json
from flask import Blueprint, request, jsonify, g
from db.database import get_sqlite_connection, DB_LOCK, init_db, log_audit, get_db_mode
from engine.lock_manager import LockManager
from api.auth import require_auth

system_bp = Blueprint("system", __name__, url_prefix="/api")
lock_mgr = LockManager()

@system_bp.route("/system-state", methods=["GET"])
def get_system_state():
    """Returns real-time data across demo tables and active lock stats."""
    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()

        cur.execute("SELECT account_id, account_number, holder_name, balance, version, updated_at FROM demo_accounts ORDER BY account_id;")
        accounts = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT ticket_id, event_name, seat_code, price, status, booked_by_user_id, version FROM demo_tickets ORDER BY ticket_id;")
        tickets = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT reservation_id, user_id, ticket_id, amount_paid, status, created_at FROM demo_reservations ORDER BY reservation_id DESC LIMIT 10;")
        reservations = [dict(r) for r in cur.fetchall()]

        conn.close()

    lock_stats = lock_mgr.get_lock_stats()

    return jsonify({
        "db_mode": get_db_mode(),
        "accounts": accounts,
        "tickets": tickets,
        "reservations": reservations,
        "locks": lock_stats
    }), 200

@system_bp.route("/system/reset", methods=["POST"])
@require_auth(roles=["ADMIN"])
def reset_system():
    """Admin endpoint to restore demo tables to pristine state (Account #1 at $1000)."""
    user_id = g.current_user.get("user_id", 1)
    lock_mgr.reset()
    init_db(reset=True)
    log_audit("SYSTEM_STATE_RESET", "SUCCESS", user_id=user_id, payload_summary="All accounts reset to $1,000.00; tickets reset to AVAILABLE.")
    return jsonify({
        "success": True,
        "message": "DBGuard state reset successfully! Account #1 balance set to $1,000.00, seats set to AVAILABLE, locks cleared."
    }), 200

@system_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """Computes real-time analytics for the dashboard metrics cards."""
    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM transaction_logs;")
        total_tx = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM conflict_logs;")
        total_conflicts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM conflict_logs WHERE conflict_type = 'DEADLOCK' AND resolution_status = 'RETRIED_SUCCESSFULLY';")
        deadlocks_resolved = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM integrity_violations;")
        integrity_violations = cur.fetchone()[0]

        conn.close()

    lock_stats = lock_mgr.get_lock_stats()
    conflict_rate = round((total_conflicts / max(1, total_tx)) * 100.0, 1)

    return jsonify({
        "total_transactions": total_tx,
        "total_conflicts": total_conflicts,
        "conflict_rate_percent": conflict_rate,
        "deadlocks_auto_resolved": deadlocks_resolved,
        "integrity_violations_blocked": integrity_violations,
        "active_locks": lock_stats["active_locks_count"],
        "avg_lock_wait_ms": lock_stats["avg_wait_ms"]
    }), 200

@system_bp.route("/monitoring-rules", methods=["GET"])
def get_rules():
    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("SELECT rule_id, rule_name, rule_type, enabled, parameters, created_at FROM monitoring_rules ORDER BY rule_id;")
        rules = []
        for r in cur.fetchall():
            item = dict(r)
            try:
                item["parameters"] = json.loads(item["parameters"])
            except Exception:
                pass
            rules.append(item)
        conn.close()
    return jsonify({"rules": rules}), 200
