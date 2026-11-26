"""
DBGuard Scenario Simulation REST Endpoints
Provides endpoints for executing:
- Lost Update (unsafe, pessimistic, optimistic, atomic)
- Double Booking (unsafe, safe)
- Deadlock & Auto-Retry
- Savepoints & Partial Rollback
- Integrity Violations (Check Constraint Negative Balance)
"""

from flask import Blueprint, request, jsonify, g
from engine.conflict_detector import ConflictDetector
from api.auth import require_auth

scenarios_bp = Blueprint("scenarios", __name__, url_prefix="/api/scenarios")
detector = ConflictDetector()

@scenarios_bp.route("/run-lost-update", methods=["POST"])
@require_auth(roles=["ADMIN", "OPERATOR"])
def run_lost_update():
    data = request.get_json() or {}
    mode = data.get("mode", "unsafe").lower()
    account_id = int(data.get("account_id", 1))
    deduct_t1 = float(data.get("deduct_t1", 100.0))
    deduct_t2 = float(data.get("deduct_t2", 200.0))
    user_id = g.current_user.get("user_id", 1)

    try:
        result = detector.run_lost_update(
            mode=mode,
            account_id=account_id,
            deduct_t1=deduct_t1,
            deduct_t2=deduct_t2,
            user_id=user_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@scenarios_bp.route("/run-double-booking", methods=["POST"])
@require_auth(roles=["ADMIN", "OPERATOR"])
def run_double_booking():
    data = request.get_json() or {}
    mode = data.get("mode", "safe").lower()
    ticket_id = int(data.get("ticket_id", 1))
    user_id = g.current_user.get("user_id", 1)

    try:
        result = detector.run_double_booking(mode=mode, ticket_id=ticket_id, user_id=user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@scenarios_bp.route("/run-deadlock", methods=["POST"])
@require_auth(roles=["ADMIN", "OPERATOR"])
def run_deadlock():
    data = request.get_json() or {}
    mode = data.get("mode", "auto_retry").lower()
    user_id = g.current_user.get("user_id", 1)

    try:
        result = detector.run_deadlock(mode=mode, user_id=user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@scenarios_bp.route("/run-savepoint", methods=["POST"])
@require_auth(roles=["ADMIN", "OPERATOR"])
def run_savepoint():
    user_id = g.current_user.get("user_id", 1)
    try:
        result = detector.run_savepoint_scenario(user_id=user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@scenarios_bp.route("/run-dirty-read", methods=["POST"])
@require_auth(roles=["ADMIN", "OPERATOR"])
def run_dirty_read():
    data = request.get_json() or {}
    mode = data.get("mode", "unsafe").lower()
    account_id = int(data.get("account_id", 1))
    user_id = g.current_user.get("user_id", 1)

    try:
        result = detector.run_dirty_read(mode=mode, account_id=account_id, user_id=user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@scenarios_bp.route("/run-integrity-violation", methods=["POST"])
@require_auth(roles=["ADMIN", "OPERATOR"])
def run_integrity_violation():
    data = request.get_json() or {}
    account_id = int(data.get("account_id", 1))
    deduct_amount = float(data.get("deduct_amount", 1500.0))
    user_id = g.current_user.get("user_id", 1)

    try:
        result = detector.run_integrity_violation_scenario(
            account_id=account_id,
            deduct_amount=deduct_amount,
            user_id=user_id
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
