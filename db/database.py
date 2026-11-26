"""
DBGuard Database Abstraction Layer
Supports:
1. Native MySQL 8.x (InnoDB Engine) via PyMySQL
2. Built-in Transactional SQLite Engine for zero-dependency local runs
"""

import os
import json
import sqlite3
import datetime
import threading
from werkzeug.security import generate_password_hash, check_password_hash

# Try importing PyMySQL
try:
    import pymysql
    import pymysql.cursors
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

DB_LOCK = threading.RLock()
SQLITE_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dbguard.sqlite3"))

def get_db_mode():
    """Detect whether to run in native MySQL mode or Built-in SQLite mode."""
    if os.getenv("DB_MODE", "").lower() == "mysql" and PYMYSQL_AVAILABLE:
        return "mysql"
    return "sqlite"

def get_mysql_connection():
    if not PYMYSQL_AVAILABLE:
        raise RuntimeError("PyMySQL is not installed.")
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        database=os.getenv("MYSQL_DB", "dbguard"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )

def get_sqlite_connection():
    """Returns a SQLite connection with row factory and foreign keys enabled."""
    conn = sqlite3.connect(SQLITE_DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_connection():
    mode = get_db_mode()
    if mode == "mysql":
        try:
            return get_mysql_connection()
        except Exception as e:
            # Fallback to sqlite if MySQL connection fails
            print(f"[DBGuard] Warning: MySQL connection failed ({e}). Falling back to built-in SQLite engine.")
            return get_sqlite_connection()
    return get_sqlite_connection()

def init_db(reset=False):
    """Initializes tables and seeds initial data."""
    with DB_LOCK:
        conn = get_sqlite_connection()
        cur = conn.cursor()

        if reset:
            tables = [
                "demo_reservations", "demo_tickets", "demo_accounts",
                "conflict_logs", "integrity_violations", "transaction_logs",
                "audit_logs", "monitoring_rules", "monitored_resources", "dbguard_users"
            ]
            for t in tables:
                cur.execute(f"DROP TABLE IF EXISTS {t};")
            conn.commit()

        # DDL for SQLite
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS dbguard_users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT CHECK(role IN ('ADMIN', 'AUDITOR', 'OPERATOR')) NOT NULL DEFAULT 'OPERATOR',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS monitored_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_name TEXT NOT NULL UNIQUE,
            resource_type TEXT CHECK(resource_type IN ('TABLE', 'ROW', 'STORED_PROCEDURE')) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS monitoring_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL UNIQUE,
            rule_type TEXT CHECK(rule_type IN ('CONCURRENCY_CONFLICT', 'INTEGRITY_CHECK', 'ISOLATION_ANOMALY', 'DEADLOCK_RISK')) NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            parameters TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS transaction_logs (
            transaction_id TEXT PRIMARY KEY,
            user_id INTEGER,
            session_id TEXT NOT NULL,
            scenario_name TEXT NOT NULL,
            isolation_level TEXT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            status TEXT CHECK(status IN ('RUNNING', 'COMMITTED', 'ROLLED_BACK', 'DEADLOCK_ABORTED', 'FAILED')) NOT NULL,
            affected_rows INTEGER DEFAULT 0,
            details TEXT,
            FOREIGN KEY (user_id) REFERENCES dbguard_users(user_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS conflict_logs (
            conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            conflict_type TEXT CHECK(conflict_type IN ('LOST_UPDATE', 'DOUBLE_BOOKING', 'DEADLOCK', 'DIRTY_READ', 'NON_REPEATABLE_READ', 'LOCK_TIMEOUT')) NOT NULL,
            severity TEXT CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')) NOT NULL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolution_status TEXT CHECK(resolution_status IN ('DETECTED_CORRUPTED', 'PREVENTED_PESSIMISTIC', 'PREVENTED_OPTIMISTIC', 'RETRIED_SUCCESSFULLY', 'ROLLED_BACK')) NOT NULL,
            details TEXT,
            FOREIGN KEY (transaction_id) REFERENCES transaction_logs(transaction_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS integrity_violations (
            violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER,
            constraint_type TEXT CHECK(constraint_type IN ('PRIMARY_KEY', 'FOREIGN_KEY', 'UNIQUE', 'CHECK_CONSTRAINT', 'BUSINESS_RULE')) NOT NULL,
            table_name TEXT NOT NULL,
            details TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES monitored_resources(resource_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            result TEXT CHECK(result IN ('SUCCESS', 'FAILURE', 'WARNING')) NOT NULL,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            payload_summary TEXT,
            FOREIGN KEY (user_id) REFERENCES dbguard_users(user_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS demo_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL UNIQUE,
            holder_name TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0.00,
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_positive_balance CHECK (balance >= 0.00)
        );

        CREATE TABLE IF NOT EXISTS demo_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            seat_code TEXT NOT NULL UNIQUE,
            price REAL NOT NULL,
            status TEXT CHECK(status IN ('AVAILABLE', 'HELD', 'BOOKED')) NOT NULL DEFAULT 'AVAILABLE',
            booked_by_user_id INTEGER NULL,
            version INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (booked_by_user_id) REFERENCES dbguard_users(user_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS demo_reservations (
            reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticket_id INTEGER NOT NULL,
            amount_paid REAL NOT NULL,
            status TEXT CHECK(status IN ('CONFIRMED', 'CANCELLED', 'PARTIAL_REFUND')) NOT NULL DEFAULT 'CONFIRMED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES dbguard_users(user_id),
            FOREIGN KEY (ticket_id) REFERENCES demo_tickets(ticket_id)
        );
        """)
        conn.commit()

        # Seed initial data if tables are empty
        cur.execute("SELECT COUNT(*) AS cnt FROM dbguard_users;")
        if cur.fetchone()[0] == 0:
            default_pwd_hash = generate_password_hash("Password123!")
            cur.executemany("""
                INSERT INTO dbguard_users (user_id, username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?, ?);
            """, [
                (1, "admin", default_pwd_hash, "System Administrator", "ADMIN"),
                (2, "auditor", default_pwd_hash, "Security Compliance Auditor", "AUDITOR"),
                (3, "operator", default_pwd_hash, "Operations Specialist", "OPERATOR")
            ])

            cur.executemany("""
                INSERT INTO monitored_resources (resource_id, resource_name, resource_type, description)
                VALUES (?, ?, ?, ?);
            """, [
                (1, "demo_accounts", "TABLE", "Core financial ledger containing customer balances and version counters"),
                (2, "demo_tickets", "TABLE", "High-concurrency event seat inventory requiring exclusive reservation controls"),
                (3, "demo_reservations", "TABLE", "Transaction receipt records supporting multi-step savepoint commits")
            ])

            cur.executemany("""
                INSERT INTO monitoring_rules (rule_id, rule_name, rule_type, enabled, parameters)
                VALUES (?, ?, ?, ?, ?);
            """, [
                (1, "Lost Update Prevention Rule", "CONCURRENCY_CONFLICT", 1, json.dumps({"mode": "ENFORCE_PESSIMISTIC_OR_OPTIMISTIC", "threshold_ms": 500})),
                (2, "Positive Balance Invariant", "INTEGRITY_CHECK", 1, json.dumps({"constraint": "CHECK_BALANCE_NON_NEGATIVE", "min_value": 0.00})),
                (3, "Double Reservation Prevention", "ISOLATION_ANOMALY", 1, json.dumps({"unique_key": ["event_name", "seat_code"], "enforce_locks": True})),
                (4, "Deadlock Auto-Recovery Rule", "DEADLOCK_RISK", 1, json.dumps({"max_retries": 3, "backoff_base_ms": 50, "backoff_max_ms": 250}))
            ])

            cur.executemany("""
                INSERT INTO demo_accounts (account_id, account_number, holder_name, balance, version)
                VALUES (?, ?, ?, ?, ?);
            """, [
                (1, "ACC-1001", "Alice Johnson", 1000.00, 1),
                (2, "ACC-1002", "Bob Smith", 1000.00, 1),
                (3, "ACC-1003", "Charlie Brown", 500.00, 1)
            ])

            cur.executemany("""
                INSERT INTO demo_tickets (ticket_id, event_name, seat_code, price, status, booked_by_user_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, [
                (1, "Tech Summit 2026", "A-101", 150.00, "AVAILABLE", None, 1),
                (2, "Tech Summit 2026", "A-102", 150.00, "AVAILABLE", None, 1),
                (3, "Tech Summit 2026", "B-201", 250.00, "AVAILABLE", None, 1),
                (4, "Tech Summit 2026", "B-202", 250.00, "AVAILABLE", None, 1)
            ])

            conn.commit()

        conn.close()

def log_audit(action, result, user_id=None, ip_address="127.0.0.1", payload_summary=""):
    """Appends an event to audit_logs."""
    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, result, ip_address, payload_summary)
            VALUES (?, ?, ?, ?, ?);
        """, (user_id, action, result, ip_address, payload_summary[:490]))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DBGuard Audit Error] {e}")

def record_conflict(transaction_id, conflict_type, severity, resolution_status, details):
    """Records a detected or resolved conflict into conflict_logs."""
    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO conflict_logs (transaction_id, conflict_type, severity, resolution_status, details)
            VALUES (?, ?, ?, ?, ?);
        """, (
            transaction_id, conflict_type, severity, resolution_status,
            json.dumps(details) if isinstance(details, (dict, list)) else str(details)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DBGuard Conflict Log Error] {e}")

def record_integrity_violation(resource_id, constraint_type, table_name, details):
    """Records a schema or business integrity violation into integrity_violations."""
    try:
        conn = get_sqlite_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO integrity_violations (resource_id, constraint_type, table_name, details)
            VALUES (?, ?, ?, ?);
        """, (
            resource_id, constraint_type, table_name,
            json.dumps(details) if isinstance(details, (dict, list)) else str(details)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DBGuard Integrity Log Error] {e}")
