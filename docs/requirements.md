# TransactionGuard Requirements & Specification

## 1. Functional Requirements

| ID | Requirement | Description | Status |
|---|---|---|---|
| FR-01 | Concurrent Workload Generation | Generate controlled multi-transaction workloads with configurable concurrency | Implemented |
| FR-02 | Controlled Execution Scheduling | Synchronize thread execution order using barriers to reproduce race conditions | Implemented |
| FR-03 | Operation Instrumentation | Capture READ, WRITE, COMMIT, and ROLLBACK operations independently | Implemented |
| FR-04 | Dependency Reconstruction | Infer WR, RW (anti-dependency), and WW directed edges between transactions | Implemented |
| FR-05 | Two-Phase Anomaly Detection | Phase 1 (Explicit errors) and Phase 2 (Dependency cycles, lost updates, skews) | Implemented |
| FR-06 | Isolation Matrix Compliance | Validate findings against PostgreSQL Read Committed, Repeatable Read, Serializable | Implemented |
| FR-07 | Business Invariant Validation | Enforce non-negative inventory, no double bookings, minimum doctor duty rules | Implemented |
| FR-08 | Root-Cause Explainability | Generate evidence-backed investigation reports with corrective SQL remediation code | Implemented |
| FR-09 | Isolation Benchmark Analytics | Compare TPS, P95 latency, abort rates across Read Committed vs Repeatable Read vs Serializable | Implemented |
| FR-10 | Live Demonstration System | One-click reproduction and verification of "The Last Item Problem" and "Write Skew" | Implemented |

---

## 2. Non-Functional Requirements

- **Reliability**: Telemetry collection does not corrupt or interfere with database state.
- **Reproducibility**: Predefined schedules execute identically across repeated runs.
- **Explainability**: Every detected anomaly provides involved transactions, affected keys, and event traces.
- **Extensibility**: Modular architecture allows adding new anomaly patterns and database engines without modifying core pipelines.
