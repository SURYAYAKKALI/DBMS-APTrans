"""
Pydantic Schemas for TransactionGuard REST API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ProjectCreate(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Primary Concurrency Project"})
    description: Optional[str] = "Testing relational isolation & anomalies"
    database_config: Optional[str] = '{"engine": "sqlite", "database": "transactionguard.db"}'

class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: Optional[str]
    database_config: str
    created_at: Optional[str]

class ConnectionTestRequest(BaseModel):
    database_url: Optional[str] = None
    engine_type: str = "sqlite"  # "postgresql" or "sqlite"

class ConnectionTestResponse(BaseModel):
    success: bool
    engine: str
    message: str
    latency_ms: float

class RunCreate(BaseModel):
    project_id: str = "PROJ-DEFAULT"
    isolation_level: str = "READ COMMITTED"  # READ COMMITTED, REPEATABLE READ, SERIALIZABLE
    workload_type: str = "lost_update"      # lost_update, write_skew, non_repeatable_read, dirty_read, read_skew, stress_concurrency
    concurrency: int = 2
    apply_mitigation: bool = False

class RunExecuteResponse(BaseModel):
    run_id: str
    status: str
    workload: str
    isolation_level: str
    mitigation_applied: bool
    duration_ms: float
    total_txns: int
    committed_txns: int
    aborted_txns: int
    anomalies_detected: int
    is_clean: bool

class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_table: str
    rule_definition: str
    severity: str = "CRITICAL"

class RuleResponse(BaseModel):
    rule_id: str
    name: str
    description: Optional[str]
    target_table: str
    rule_definition: str
    severity: str
    enabled: bool
