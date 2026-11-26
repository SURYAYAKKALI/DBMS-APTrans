"""
SQLAlchemy models for Business Application & Transaction Monitoring
"""

import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database.connection import Base

# ============================================================================
# BUSINESS APPLICATION MODELS
# ============================================================================

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Equipment(Base):
    __tablename__ = "equipment"

    equipment_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    available_quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(50), default="AVAILABLE")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Inventory(Base):
    __tablename__ = "inventory"

    inventory_id = Column(String(64), primary_key=True)
    equipment_id = Column(String(64), ForeignKey("equipment.equipment_id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=False)
    equipment_id = Column(String(64), ForeignKey("equipment.equipment_id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="CONFIRMED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=False)
    equipment_id = Column(String(64), ForeignKey("equipment.equipment_id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    total_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="PENDING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), ForeignKey("orders.order_id"), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="COMPLETED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Doctor(Base):
    __tablename__ = "doctors"

    doctor_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    on_duty = Column(Boolean, nullable=False, default=True)
    shift_date = Column(String(20), nullable=False, default="2026-11-02")

# ============================================================================
# TRANSACTION MONITORING MODELS
# ============================================================================

class TestProject(Base):
    __tablename__ = "test_projects"

    project_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    database_config = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TestRun(Base):
    __tablename__ = "test_runs"

    run_id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("test_projects.project_id"), nullable=False)
    isolation_level = Column(String(50), nullable=False)
    workload_type = Column(String(100), nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="RUNNING")
    total_txns = Column(Integer, default=0)
    committed_txns = Column(Integer, default=0)
    aborted_txns = Column(Integer, default=0)
    anomalies_detected = Column(Integer, default=0)
    execution_duration_ms = Column(Float, default=0.0)
    summary = Column(Text, nullable=True)

class TransactionRecord(Base):
    __tablename__ = "transactions"

    txn_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("test_runs.run_id"), nullable=False)
    session_id = Column(String(64), nullable=False)
    isolation_level = Column(String(50), nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    outcome = Column(String(50), default="ACTIVE")
    error_message = Column(Text, nullable=True)

class OperationEvent(Base):
    __tablename__ = "operation_events"

    event_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("test_runs.run_id"), nullable=False)
    txn_id = Column(String(64), ForeignKey("transactions.txn_id"), nullable=False)
    session_id = Column(String(64), nullable=False)
    sequence = Column(Integer, nullable=False)
    operation_type = Column(String(50), nullable=False)  # READ, WRITE, UPDATE, INSERT, COMMIT, ROLLBACK
    table_name = Column(String(100), nullable=False)
    row_id = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    version = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(50), default="PENDING")

class DataVersion(Base):
    __tablename__ = "data_versions"

    version_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("test_runs.run_id"), nullable=False)
    table_name = Column(String(100), nullable=False)
    row_id = Column(String(100), nullable=False)
    version = Column(Integer, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    created_by_txn = Column(String(64), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Dependency(Base):
    __tablename__ = "dependencies"

    edge_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("test_runs.run_id"), nullable=False)
    source_txn = Column(String(64), nullable=False)
    target_txn = Column(String(64), nullable=False)
    dependency_type = Column(String(10), nullable=False)  # WR, RW, WW
    table_name = Column(String(100), nullable=False)
    row_id = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    is_cycle_member = Column(Boolean, default=False)

class Anomaly(Base):
    __tablename__ = "anomalies"

    anomaly_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("test_runs.run_id"), nullable=False)
    type = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)
    involved_txns = Column(Text, nullable=False)
    affected_records = Column(Text, nullable=False)
    expected_behavior = Column(Text, nullable=False)
    observed_behavior = Column(Text, nullable=False)
    evidence = Column(Text, nullable=False)
    suggested_fix = Column(Text, nullable=False)
    status = Column(String(50), default="DETECTED")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class BusinessRule(Base):
    __tablename__ = "business_rules"

    rule_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_table = Column(String(100), nullable=False)
    rule_definition = Column(Text, nullable=False)
    severity = Column(String(50), default="CRITICAL")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TestSchedule(Base):
    __tablename__ = "test_schedules"

    schedule_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("test_runs.run_id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    txn_id = Column(String(64), nullable=False)
    operation_payload = Column(Text, nullable=False)
    barrier_phase = Column(Integer, default=0)
