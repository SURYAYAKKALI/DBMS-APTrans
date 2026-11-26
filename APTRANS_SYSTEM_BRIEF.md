# APTrans System Brief: What We Have & Why

This brief provides a concise, high-density architectural breakdown of what components have been constructed in our reconstruction of the APTrans framework and the theoretical/engineering justifications for each.

---

## 1. What We Have & Why We Have It

### A. The Complete 46-Pattern Anomaly Repository (`aptrans/patterns.py`)
- **What We Have**:
  - The 6 canonical anomalies from Table 2: Dirty Write ($G_0$), Dirty Read ($A_1$), Lost Update ($P_4$), Non-Repeatable Read ($A_2$), Write Skew ($A5B$), Read Skew ($A5A$).
  - All 40 extended anomaly patterns from Table 3, representing every valid interleaving of 2 concurrent transactions operating across 2 shared data items ($x, y$) with operation sequence, Adya dependency annotations ($ww, wr, rw$), and disallowed isolation levels (`ALL`, `RC, RR, SER`, `RR, SER`, `SER`).
- **Why We Have It**:
  - Random transaction testing (e.g. SQLsmith, TxCheck, Troc) has a vanishingly small probability of generating the exact sequences and shared data overlap required to trigger concurrency bugs. Formal patterns provide targeted templates that maximize bug-triggering probability with minimal test generation waste.

---

### B. Formal Three-Dimensional Constraint Extractor (`aptrans/patterns.py`)
- **What We Have**:
  - Algorithmic parser decomposing any anomaly string into:
    1. **Statement Type Constraint ($Cstr_1$)**: $\langle(R, n_R), (W, n_W), (B, n_B), (C, n_C)\rangle$ per transaction.
    2. **Data Access Constraint ($Cstr_2$)**: Mapping operations $R_i^k, W_i^k$ to abstract variables $x, y$.
    3. **Schedule Order Constraint ($Cstr_3$)**: Dispatch sequence $[t_1, \dots, t_m]$.
- **Why We Have It**:
  - Complex multi-transaction patterns cannot be generated as monolithic blocks. Decomposing patterns into orthogonal dimensions allows the transaction synthesizer (Algorithm 1) to operate modularly while preserving the exact temporal and data conflict semantics of the anomaly.

---

### C. Multi-Table Schema Synthesizer with Synthetic Columns (`aptrans/schema_generator.py`)
- **What We Have**:
  - Schema builder injecting synthetic `row_id` (globally unique row identifier) and `version` (optimistic version counter).
  - Candidate key matcher across tables creating valid foreign key relationships.
  - Primary key data logging ensuring seed INSERTs respect referential integrity.
  - Multi-table JOIN generator supporting `INNER`, `LEFT`, `RIGHT`, and `CROSS` joins.
  - Expression type constraint checker.
- **Why We Have It**:
  - Concurrency bugs in production databases often occur across joined tables and foreign keys. The synthetic `row_id` and `version` columns provide unambiguous traceability for data dependencies ($ww, wr, rw$) without mutating the transaction's core SQL semantics. The type checker solves the pervasive type-mismatch semantic errors found in raw SQLancer.

---

### D. Algorithm 1: Pattern-Guided Transaction Generator (`aptrans/transaction_generator.py`)
- **What We Have**:
  - Three-stage synthesis pipeline: Statement Selection $\to$ Condition Alignment $\to$ Transaction Composition.
  - Condition alignment maps abstract variables ($x, y$) to specific row keys (e.g., `WHERE row_id = 1`) or full-table scans.
  - Automatic packaging with transaction framing (`BEGIN`, `SET TRANSACTION ISOLATION LEVEL ...`, `COMMIT`, `ROLLBACK`).
- **Why We Have It**:
  - Without condition alignment, randomly generated statements touch disparate rows, resulting in zero inter-transaction conflict. Condition alignment guarantees conflicting accesses to shared resources, transforming abstract anomaly formulas into executable SQL workloads.

---

### E. Algorithm 2: Execution Coordinator & Dual-Mode Recorder (`aptrans/execution_engine.py`)
- **What We Have**:
  - Multi-session concurrency scheduler enforcing the dispatch order dictated by $Cstr_3$.
  - Blocked transaction handling via wait-list queue (`waitTxn`) and lock-release resumption.
  - Dual-mode recording:
    1. SQL trigger generator logging modifications into `{table}_log`.
    2. Engine-level WAL/audit observer preserving uncommitted and rolled-back writes to resolve the **Trigger Rollback Fallacy**.
- **Why We Have It**:
  - Databases dynamically block and queue conflicting transactions. Simple sequential execution cannot simulate concurrent interleavings. Algorithm 2 accurately mirrors real-world concurrency while guaranteeing full traceability of intermediate states.

---

### F. Two-Phase Bug Detection Oracle (`aptrans/detector.py`)
- **What We Have**:
  - **Phase 1**: Explicit error filter capturing server crashes, assertion failures, and SQL error codes, while discarding unrelated syntax errors and expected deadlocks.
  - **Phase 2**: Dynamic Dependency Graph ($G = (N, E)$) construction with $ww$, $wr$ (including version-visibility verification), and $rw$ edges.
  - Pattern matching engine searching $G$ for anomaly paths and verifying against the active isolation level.
- **Why We Have It**:
  - Concurrency bugs are almost always silent: the database returns clean exit codes while silently violating isolation invariants. Implicit dependency graph checking uncovers these silent inconsistencies with mathematical precision and zero guesswork.

---

### G. Real-World Case Study Replay Harness (`aptrans/case_studies.py`)
- **What We Have**:
  - Faithful, reproducible execution harnesses for:
    1. **MySQL Bug #117835** (Read Committed Dirty Read).
    2. **OceanBase Bug #2248** (Repeatable Read Non-Repeatable Read).
    3. **MariaDB Bug #36330** (Serializable auto-increment subquery anomaly).
- **Why We Have It**:
  - Validates that the reconstructed engine is not merely theoretical, but can deterministically trigger and detect the exact real-world bugs reported by the authors to the database maintainers.

---

### H. Interactive Web Dashboard & Visualizer (`static/` & `api/routes_aptrans.py`)
- **What We Have**:
  - Comprehensive 8-tab visual console providing interactive exploration of the 46 patterns, dynamic test generation, real-time schedule stepping, graph visualization, benchmark analytics, and academic critique.
- **Why We Have It**:
  - Provides a rich, human-verifiable demonstration environment enabling professors, researchers, and database engineers to explore, interact with, and stress-test the entire APTrans pipeline.
