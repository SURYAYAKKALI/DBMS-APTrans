-- TransactionGuard Seed Data
-- Initial setup for inventory, equipment, users, and core business invariants

-- Users
INSERT OR REPLACE INTO users (user_id, name, email) VALUES
('USR-001', 'Alice Engineering', 'alice@transguard.internal'),
('USR-002', 'Bob DevOps', 'bob@transguard.internal'),
('USR-003', 'Charlie Researcher', 'charlie@transguard.internal'),
('USR-004', 'Diana Admin', 'diana@transguard.internal');

-- Equipment
INSERT OR REPLACE INTO equipment (equipment_id, name, quantity, available_quantity, status) VALUES
('EQ-LAPTOP-01', 'MacBook Pro M3 Max (Dev Edition)', 1, 1, 'AVAILABLE'),
('EQ-PROJ-01', '4K Laser Conference Projector', 3, 3, 'AVAILABLE'),
('EQ-SERVER-01', 'Dell PowerEdge R750 Database Node', 2, 2, 'AVAILABLE'),
('EQ-GPU-01', 'NVIDIA H100 GPU Workstation', 1, 1, 'AVAILABLE');

-- Inventory
INSERT OR REPLACE INTO inventory (inventory_id, equipment_id, quantity, version) VALUES
('INV-LAPTOP-01', 'EQ-LAPTOP-01', 1, 1),
('INV-PROJ-01', 'EQ-PROJ-01', 3, 1),
('INV-SERVER-01', 'EQ-SERVER-01', 2, 1),
('INV-GPU-01', 'EQ-GPU-01', 1, 1);

-- Doctors (for Write Skew demonstrations)
INSERT OR REPLACE INTO doctors (doctor_id, name, on_duty, shift_date) VALUES
('DOC-001', 'Dr. Meredith Grey', 1, '2026-11-02'),
('DOC-002', 'Dr. Derek Shepherd', 1, '2026-11-02');

-- Default Testing Project
INSERT OR REPLACE INTO test_projects (project_id, name, description, database_config) VALUES
('PROJ-DEFAULT', 'Primary Transaction Concurrency Lab', 'Production-grade PostgreSQL & SQLite validation environment', '{"engine": "sqlite", "database": "transactionguard.db", "pool_size": 10}');

-- Standard Business Consistency Invariant Rules
INSERT OR REPLACE INTO business_rules (rule_id, name, description, target_table, rule_definition, severity, enabled) VALUES
('RULE-NON-NEGATIVE-STOCK', 'Inventory Quantity Non-Negative', 'Inventory quantity must never fall below zero (prevent overselling)', 'inventory', 'quantity >= 0', 'CRITICAL', 1),
('RULE-NO-OVERLAPPING-RESERVATIONS', 'Exclusive Equipment Reservation', 'Confirmed reservations for the same equipment cannot overlap in time', 'reservations', 'no_time_overlap', 'CRITICAL', 1),
('RULE-AT-LEAST-ONE-ON-DUTY', 'At Least One Doctor On Duty', 'At all times during a shift, at least one doctor must remain on active duty', 'doctors', 'sum(on_duty) >= 1', 'HIGH', 1),
('RULE-BALANCE-CONSERVATION', 'Payment-Order Total Conservation', 'Sum of completed payments must match total order amounts', 'payments', 'sum(payment.amount) == sum(orders.total_amount)', 'HIGH', 1);
