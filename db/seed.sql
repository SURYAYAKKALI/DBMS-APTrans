-- DBGuard Initial Seed Data

-- 1. Default Users with different RBAC roles
-- Default password: "Password123!" (hashed via werkzeug pbkdf2:sha256)
-- Hash generated for "Password123!": 'scrypt:32768:8:1$K7oH$12345...'
-- We will also seed programmatic hashes in Python, but here are the SQL seed records:
INSERT INTO dbguard_users (user_id, username, password_hash, full_name, role) VALUES
(1, 'admin', 'scrypt:32768:8:1$dbguard$a7620ddb27ec7ad7818e11ec55239e2f8ec584e031a0ea4c16a65e79ff738221b22894ba1b7e6c0c201d4a89608b4eb905fa868e7d23d91cf9fa5776d6537bf4', 'System Administrator', 'ADMIN'),
(2, 'auditor', 'scrypt:32768:8:1$dbguard$a7620ddb27ec7ad7818e11ec55239e2f8ec584e031a0ea4c16a65e79ff738221b22894ba1b7e6c0c201d4a89608b4eb905fa868e7d23d91cf9fa5776d6537bf4', 'Security Compliance Auditor', 'AUDITOR'),
(3, 'operator', 'scrypt:32768:8:1$dbguard$a7620ddb27ec7ad7818e11ec55239e2f8ec584e031a0ea4c16a65e79ff738221b22894ba1b7e6c0c201d4a89608b4eb905fa868e7d23d91cf9fa5776d6537bf4', 'Operations Specialist', 'OPERATOR');

-- 2. Monitored Resources
INSERT INTO monitored_resources (resource_id, resource_name, resource_type, description) VALUES
(1, 'demo_accounts', 'TABLE', 'Core financial ledger containing customer balances and version counters'),
(2, 'demo_tickets', 'TABLE', 'High-concurrency event seat inventory requiring exclusive reservation controls'),
(3, 'demo_reservations', 'TABLE', 'Transaction receipt records supporting multi-step savepoint commits');

-- 3. Monitoring Rules
INSERT INTO monitoring_rules (rule_id, rule_name, rule_type, enabled, parameters) VALUES
(1, 'Lost Update Prevention Rule', 'CONCURRENCY_CONFLICT', TRUE, '{"mode": "ENFORCE_PESSIMISTIC_OR_OPTIMISTIC", "threshold_ms": 500}'),
(2, 'Positive Balance Invariant', 'INTEGRITY_CHECK', TRUE, '{"constraint": "CHECK_BALANCE_NON_NEGATIVE", "min_value": 0.00}'),
(3, 'Double Reservation Prevention', 'ISOLATION_ANOMALY', TRUE, '{"unique_key": ["event_name", "seat_code"], "enforce_locks": true}'),
(4, 'Deadlock Auto-Recovery Rule', 'DEADLOCK_RISK', TRUE, '{"max_retries": 3, "backoff_base_ms": 50, "backoff_max_ms": 250}');

-- 4. Initial Bank Accounts (Account #1 starts at $1,000.00 per presentation script)
INSERT INTO demo_accounts (account_id, account_number, holder_name, balance, version) VALUES
(1, 'ACC-1001', 'Alice Johnson', 1000.00, 1),
(2, 'ACC-1002', 'Bob Smith', 1000.00, 1),
(3, 'ACC-1003', 'Charlie Brown', 500.00, 1);

-- 5. Initial Event Tickets
INSERT INTO demo_tickets (ticket_id, event_name, seat_code, price, status, booked_by_user_id, version) VALUES
(1, 'Tech Summit 2026', 'A-101', 150.00, 'AVAILABLE', NULL, 1),
(2, 'Tech Summit 2026', 'A-102', 150.00, 'AVAILABLE', NULL, 1),
(3, 'Tech Summit 2026', 'B-201', 250.00, 'AVAILABLE', NULL, 1),
(4, 'Tech Summit 2026', 'B-202', 250.00, 'AVAILABLE', NULL, 1);
