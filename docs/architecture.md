# TransactionGuard Architecture Specification

## 1. System Overview

TransactionGuard is an intelligent database transaction anomaly detection and concurrency assurance platform. It provides a controlled execution environment to generate concurrent transaction workloads, capture fine-grained transactional telemetry, reconstruct transaction dependencies, detect isolation-level violations, and validate application business invariants.

```mermaid
flowchart TD
    subgraph UI ["User Interface Layer"]
        Dashboard["SaaS Web Dashboard (Next.js / HTML5)"]
    end

    subgraph API ["API & Coordination Layer (FastAPI)"]
        ProjectsAPI["/api/projects"]
        RunsAPI["/api/runs"]
        AnomaliesAPI["/api/anomalies"]
        AnalyticsAPI["/api/analytics"]
        DemoAPI["/api/demo"]
    end

    subgraph Core ["Core Execution & Scheduling Engine"]
        WorkloadGen["Workload Generator (E1-E6)"]
        Scheduler["Controlled Scheduler (Barrier & Event Sync)"]
        Instrumentation["Transparent Session Interceptor"]
        EventCollector["Independent Telemetry Store"]
    end

    subgraph Detection ["Two-Phase Anomaly Detection Engine"]
        Phase1["Phase 1: Explicit Error Capturing (Crashes, Deadlocks, Aborts)"]
        Phase2["Phase 2: Implicit Anomaly Detection"]
        HistRecon["Stage 1: History Reconstruction"]
        DepBuilder["Stage 2: Dependency Builder (WR, RW, WW Graphs)"]
        PatternMatch["Stage 3: Pattern Matcher (Cycles, Lost Updates, Skew)"]
        IsoValidator["Stage 4: PostgreSQL Isolation Matrix Validator"]
        InvEngine["Business Invariant Verifier"]
    end

    subgraph DB ["Database Layer"]
        BusinessDB["Business Schema (Inventory, Equipment, Orders, Doctors)"]
        TelemetryDB["Monitoring Schema (Runs, Events, Dependencies, Anomalies)"]
    end

    Dashboard --> API
    API --> Core
    Core --> DB
    Core --> Detection
    Detection --> API
```

---

## 2. Key Components

### 2.1 Independent Telemetry Collector (`backend/core/event_collector.py`)
Database triggers written inside a transaction lose their logged events if the transaction rolls back. TransactionGuard uses an application-level telemetry interceptor that captures:
- Transaction ID & Session ID
- Global sequence number
- Operation type (BEGIN, READ, WRITE, COMMIT, ROLLBACK)
- Target table and row ID
- Old value and new value
- Monotonic version identifier
- Status & error diagnostics

### 2.2 Controlled Multi-Threaded Scheduler (`backend/core/transaction_scheduler.py`)
Utilizes Python `threading.Barrier` and `threading.Event` across independent database connections to enforce exact, reproducible execution interleavings.

### 2.3 Dependency Graph Engine (`backend/detection/dependency_builder.py`)
Reconstructs Adya's transaction dependency model:
- **Write-Read (WR)**: $T_1$ writes version $V$, $T_2$ reads $V$.
- **Read-Write (RW)**: $T_1$ reads version $V$, $T_2$ writes version $V' > V$ (anti-dependency).
- **Write-Write (WW)**: $T_1$ writes version $V$, $T_2$ overwrites with $V'$.

Directed graphs are analyzed using NetworkX for cycle detection and exported into React Flow compatible node and edge structures.
