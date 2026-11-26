-- DBGuard Schema Definition (MySQL 8.x InnoDB Compatible)
-- Database Engine: InnoDB with row-level locking, foreign key constraints & check constraints

CREATE DATABASE IF NOT EXISTS dbguard;
USE dbguard;

-- Drop in reverse dependency order for clean re-creation
DROP TABLE IF EXISTS demo_reservations;
DROP TABLE IF EXISTS demo_tickets;
DROP TABLE IF EXISTS demo_accounts;
DROP TABLE IF EXISTS conflict_logs;
DROP TABLE IF EXISTS integrity_violations;
DROP TABLE IF EXISTS transaction_logs;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS monitoring_rules;
DROP TABLE IF EXISTS monitored_resources;
DROP TABLE IF EXISTS dbguard_users;

-- ========================================================
-- 1. DBGuard System / Metadata Tables
-- ========================================================

-- User management and Role-Based Access Control
CREATE TABLE dbguard_users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('ADMIN', 'AUDITOR', 'OPERATOR') NOT NULL DEFAULT 'OPERATOR',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Monitored Resources Registry
CREATE TABLE monitored_resources (
    resource_id INT AUTO_INCREMENT PRIMARY KEY,
    resource_name VARCHAR(100) NOT NULL UNIQUE,
    resource_type ENUM('TABLE', 'ROW', 'STORED_PROCEDURE') NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Configurable Monitoring Rules
CREATE TABLE monitoring_rules (
    rule_id INT AUTO_INCREMENT PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL UNIQUE,
    rule_type ENUM('CONCURRENCY_CONFLICT', 'INTEGRITY_CHECK', 'ISOLATION_ANOMALY', 'DEADLOCK_RISK') NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    parameters JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Transaction Lifecycle Logs
CREATE TABLE transaction_logs (
    transaction_id VARCHAR(64) PRIMARY KEY,
    user_id INT,
    session_id VARCHAR(64) NOT NULL,
    scenario_name VARCHAR(100) NOT NULL,
    isolation_level VARCHAR(30) NOT NULL,
    start_time TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    end_time TIMESTAMP(6) NULL,
    status ENUM('RUNNING', 'COMMITTED', 'ROLLED_BACK', 'DEADLOCK_ABORTED', 'FAILED') NOT NULL,
    affected_rows INT DEFAULT 0,
    details JSON,
    FOREIGN KEY (user_id) REFERENCES dbguard_users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Detected Conflict Logs
CREATE TABLE conflict_logs (
    conflict_id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(64),
    conflict_type ENUM('LOST_UPDATE', 'DOUBLE_BOOKING', 'DEADLOCK', 'DIRTY_READ', 'NON_REPEATABLE_READ', 'LOCK_TIMEOUT') NOT NULL,
    severity ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL,
    detected_at TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    resolution_status ENUM('DETECTED_CORRUPTED', 'PREVENTED_PESSIMISTIC', 'PREVENTED_OPTIMISTIC', 'RETRIED_SUCCESSFULLY', 'ROLLED_BACK') NOT NULL,
    details JSON,
    FOREIGN KEY (transaction_id) REFERENCES transaction_logs(transaction_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Integrity Constraint Violations
CREATE TABLE integrity_violations (
    violation_id INT AUTO_INCREMENT PRIMARY KEY,
    resource_id INT,
    constraint_type ENUM('PRIMARY_KEY', 'FOREIGN_KEY', 'UNIQUE', 'CHECK_CONSTRAINT', 'BUSINESS_RULE') NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    details JSON,
    detected_at TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (resource_id) REFERENCES monitored_resources(resource_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- System Audit Logs
CREATE TABLE audit_logs (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    result ENUM('SUCCESS', 'FAILURE', 'WARNING') NOT NULL,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payload_summary VARCHAR(500),
    FOREIGN KEY (user_id) REFERENCES dbguard_users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ========================================================
-- 2. Demonstration Domain Tables
-- ========================================================

-- Bank Accounts Table (Lost Update & Negative Balance Testing)
CREATE TABLE demo_accounts (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    account_number VARCHAR(20) NOT NULL UNIQUE,
    holder_name VARCHAR(100) NOT NULL,
    balance DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    version INT NOT NULL DEFAULT 1,  -- Optimistic lock counter
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_positive_balance CHECK (balance >= 0.00)
) ENGINE=InnoDB;

-- Ticket Inventory (Double Booking & Deadlock Testing)
CREATE TABLE demo_tickets (
    ticket_id INT AUTO_INCREMENT PRIMARY KEY,
    event_name VARCHAR(100) NOT NULL,
    seat_code VARCHAR(10) NOT NULL UNIQUE,
    price DECIMAL(8, 2) NOT NULL,
    status ENUM('AVAILABLE', 'HELD', 'BOOKED') NOT NULL DEFAULT 'AVAILABLE',
    booked_by_user_id INT NULL,
    version INT NOT NULL DEFAULT 1,
    CONSTRAINT fk_booked_user FOREIGN KEY (booked_by_user_id) 
        REFERENCES dbguard_users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Reservations Table (Multi-step transaction & Savepoint testing)
CREATE TABLE demo_reservations (
    reservation_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ticket_id INT NOT NULL,
    amount_paid DECIMAL(8, 2) NOT NULL,
    status ENUM('CONFIRMED', 'CANCELLED', 'PARTIAL_REFUND') NOT NULL DEFAULT 'CONFIRMED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES dbguard_users(user_id),
    FOREIGN KEY (ticket_id) REFERENCES demo_tickets(ticket_id)
) ENGINE=InnoDB;
