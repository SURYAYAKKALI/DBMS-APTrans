"""
DBGuard Flask Web Application & REST API
Integrates:
- Real-time Concurrency Simulation & Conflict Observability
- Role-Based Access Control (Admin, Auditor, Operator)
- Interactive Dashboard Frontend
"""

import os
import sys

# Ensure repository root is on sys.path regardless of execution entrypoint
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, send_from_directory, request, jsonify, g
from flask_cors import CORS
from db.database import init_db, log_audit
from api.auth import authenticate_user, generate_token, require_auth, ROLE_PERMISSIONS
from api.routes_scenarios import scenarios_bp
from api.routes_audit import audit_bp
from api.routes_system import system_bp
from api.routes_aptrans import aptrans_bp

def create_app():
    static_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    app = Flask(__name__, static_folder=static_folder, static_url_path="")
    CORS(app)

    # Initialize database on startup
    init_db(reset=False)

    # Register blueprints
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(aptrans_bp)

    @app.route("/")
    def index():
        return send_from_directory(static_folder, "index.html")

    # Auth endpoints
    @app.route("/api/auth/login", methods=["POST"])
    def login():
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        user = authenticate_user(username, password)
        if not user:
            log_audit("LOGIN_FAILED", "FAILURE", payload_summary=f"Invalid login attempt for username '{username}'")
            return jsonify({"error": "Invalid username or password"}), 401

        token = generate_token(user["user_id"], user["username"], user["role"], user["full_name"])
        log_audit("LOGIN_SUCCESS", "SUCCESS", user_id=user["user_id"], payload_summary=f"User '{username}' logged in as {user['role']}")

        return jsonify({
            "token": token,
            "user": user
        }), 200

    @app.route("/api/auth/me", methods=["GET"])
    @require_auth()
    def me():
        return jsonify({"user": g.current_user}), 200

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found"}), 404
        return send_from_directory(static_folder, "index.html")

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    print(f"==================================================")
    print(f"  DBGuard Server is running at http://127.0.0.1:{port}")
    print(f"==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
