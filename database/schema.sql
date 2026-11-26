-- TransactionGuard Unified Database Schema
-- Comprises:
-- 1. Business Application Schema (Inventory & Reservation System)
-- 2. Transaction Monitoring & Assurance Schema

-- ============================================================================
-- 1. BUSINESS APPLICATION SCHEMA
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    available_quantity INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(50) DEFAULT 'AVAILABLE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id VARCHAR(64) PRIMARY KEY,
    equipment_id VARCHAR(64) NOT NULL REFERENCES equipment(equipment_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    equipment_id VARCHAR(64) NOT NULL REFERENCES equipment(equipment_id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'CONFIRMED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    equipment_id VARCHAR(64) NOT NULL REFERENCES equipment(equipment_id),
    quantity INTEGER NOT NULL DEFAULT 1,
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL REFERENCES orders(order_id),
    amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Doctor On Duty Table (for Write Skew canonical demonstration)
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    on_duty BOOLEAN NOT NULL DEFAULT TRUE,
    shift_date VARCHAR(20) NOT NULL DEFAULT '2026-11-02'
);

-- ============================================================================
-- 2. TRANSACTION MONITORING & ASSURANCE SCHEMA
-- ============================================================================

CREATE TABLE IF NOT EXISTS test_projects (
    project_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    database_config TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES test_projects(project_id) ON DELETE CASCADE,
    isolation_level VARCHAR(50) NOT NULL,
    workload_type VARCHAR(100) NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'RUNNING',
    total_txns INTEGER DEFAULT 0,
    committed_txns INTEGER DEFAULT 0,
    aborted_txns INTEGER DEFAULT 0,
    anomalies_detected INTEGER DEFAULT 0,
    execution_duration_ms DOUBLE PRECISION DEFAULT 0.0,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    session_id VARCHAR(64) NOT NULL,
    isolation_level VARCHAR(50) NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    outcome VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS operation_events (
    event_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    txn_id VARCHAR(64) NOT NULL REFERENCES transactions(txn_id) ON DELETE CASCADE,
    session_id VARCHAR(64) NOT NULL,
    sequence INTEGER NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    row_id VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    version INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS data_versions (
    version_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    table_name VARCHAR(100) NOT NULL,
    row_id VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_by_txn VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dependencies (
    edge_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    source_txn VARCHAR(64) NOT NULL,
    target_txn VARCHAR(64) NOT NULL,
    dependency_type VARCHAR(10) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    row_id VARCHAR(100) NOT NULL,
    details TEXT,
    is_cycle_member BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    involved_txns TEXT NOT NULL,
    affected_records TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    observed_behavior TEXT NOT NULL,
    evidence TEXT NOT NULL,
    suggested_fix TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DETECTED',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_rules (
    rule_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    target_table VARCHAR(100) NOT NULL,
    rule_definition TEXT NOT NULL,
    severity VARCHAR(50) NOT NULL DEFAULT 'CRITICAL',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_schedules (
    schedule_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES test_runs(run_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    txn_id VARCHAR(64) NOT NULL,
    operation_payload TEXT NOT NULL,
    barrier_phase INTEGER DEFAULT 0
);
