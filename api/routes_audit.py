"""
DBGuard Audit, Conflict & Compliance REST Endpoints
Allows Auditor, Admin, and Operator to inspect telemetry records.
"""

import json
from flask import Blueprint, request, jsonify, g
from db.database import get_sqlite_connection, DB_LOCK
from api.auth import require_auth

audit_bp = Blueprint("audit", __name__, url_prefix="/api")

@audit_bp.route("/audit-logs", methods=["GET"])
@require_auth(roles=["ADMIN", "AUDITOR"])
def get_audit_logs():
    limit = int(request.args.get("limit", 100))
    action_filter = request.args.get("action")
    result_filter = request.args.get("result")

    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        query = "SELECT audit_id, user_id, action, result, ip_address, timestamp, payload_summary FROM audit_logs"
        params = []
        conditions = []

        if action_filter:
            conditions.append("action LIKE ?")
            params.append(f"%{action_filter}%")
        if result_filter:
            conditions.append("result = ?")
            params.append(result_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY audit_id DESC LIMIT ?;"
        params.append(limit)

        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

    return jsonify({"count": len(rows), "logs": rows}), 200

@audit_bp.route("/conflicts", methods=["GET"])
@require_auth(roles=["ADMIN", "AUDITOR", "OPERATOR"])
def get_conflicts():
    limit = int(request.args.get("limit", 50))
    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT conflict_id, transaction_id, conflict_type, severity, detected_at, resolution_status, details
            FROM conflict_logs
            ORDER BY conflict_id DESC
            LIMIT ?;
        """, (limit,))
        rows = []
        for r in cur.fetchall():
            item = dict(r)
            try:
                item["details"] = json.loads(item["details"])
            except Exception:
                pass
            rows.append(item)
        conn.close()

    return jsonify({"count": len(rows), "conflicts": rows}), 200

@audit_bp.route("/integrity-violations", methods=["GET"])
@require_auth(roles=["ADMIN", "AUDITOR", "OPERATOR"])
def get_integrity_violations():
    limit = int(request.args.get("limit", 50))
    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT violation_id, resource_id, constraint_type, table_name, details, detected_at
            FROM integrity_violations
            ORDER BY violation_id DESC
            LIMIT ?;
        """, (limit,))
        rows = []
        for r in cur.fetchall():
            item = dict(r)
            try:
                item["details"] = json.loads(item["details"])
            except Exception:
                pass
            rows.append(item)
        conn.close()

    return jsonify({"count": len(rows), "violations": rows}), 200

@audit_bp.route("/transaction-logs", methods=["GET"])
@require_auth(roles=["ADMIN", "AUDITOR", "OPERATOR"])
def get_transaction_logs():
    limit = int(request.args.get("limit", 50))
    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT transaction_id, user_id, session_id, scenario_name, isolation_level, start_time, end_time, status, affected_rows, details
            FROM transaction_logs
            ORDER BY start_time DESC
            LIMIT ?;
        """, (limit,))
        rows = []
        for r in cur.fetchall():
            item = dict(r)
            try:
                item["details"] = json.loads(item["details"])
            except Exception:
                pass
            rows.append(item)
        conn.close()

    return jsonify({"count": len(rows), "transactions": rows}), 200
