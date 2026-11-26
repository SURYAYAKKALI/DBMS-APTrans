"""
Comprehensive Pytest Verification Suite for APTrans
Paper: "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026)

Tests:
1. 46 Pattern Specifications and Constraint Extraction (Cstr1, Cstr2, Cstr3)
2. Schema & Multi-table Referential Generator (row_id, version, FK candidate matching, JOINs)
3. Algorithm 1: Pattern-Guided Transaction Synthesizer & Condition Alignment
4. Algorithm 2: Execution Coordinator with waitTxn queue & dual-mode recording
5. Dynamic Dependency Graph G = (N, E) Construction (ww, wr, rw dependencies)
6. Two-Phase Detector (Phase 1 explicit error filtering + Phase 2 implicit pattern matching)
7. Case Study 1: MySQL Bug #117835 (Dirty Read at RC)
8. Case Study 2: OceanBase Bug #2248 (Non-Repeatable Read at RR with Consistent Snapshot)
9. Case Study 3: MariaDB Bug #36330 (Auto-Increment Serialization Anomaly at SER)
10. Empirical Benchmark Replay & Ablation Studies (Table 5, Table 6, Table 7)
11. REST API Endpoints Verification
"""

import pytest
from aptrans.patterns import (
    ALL_PATTERNS, CANONICAL_PATTERNS, EXTENDED_PATTERNS, 
    get_pattern, list_patterns, AnomalyPattern
)
from aptrans.schema_generator import SchemaGenerator, DatabaseSchema
from aptrans.transaction_generator import TransactionGenerator, TransactionCase
from aptrans.execution_engine import ExecutionEngine, ExecutionTrace
from aptrans.detector import TwoPhaseDetector, DependencyGraph, DependencyEdge
from aptrans.case_studies import CaseStudyReplayer
from aptrans.benchmark_replay import get_benchmark_data
from api.app import create_app


# =====================================================================
# 1. Pattern Formalism & Constraint Tests
# =====================================================================
def test_all_patterns_loaded():
    assert len(ALL_PATTERNS) == 46
    assert len(CANONICAL_PATTERNS) == 6
    assert len(EXTENDED_PATTERNS) == 40


def test_pattern_constraints_extraction():
    p = get_pattern("C-LU")  # Lost update: R1[x0] W2[x1] C2 W1[x2] C1
    assert p is not None
    assert p.cstr1[1] == {"R": 1, "W": 1, "B": 0, "C": 1}
    assert p.cstr1[2] == {"R": 0, "W": 1, "B": 0, "C": 1}
    assert p.cstr3 == [1, 2, 2, 1, 1]
    assert len(p.cstr2) == 3  # R1[x0], W2[x1], W1[x2]


def test_isolation_disallowance_matrix():
    lu = get_pattern("C-LU")
    assert not lu.is_disallowed("READ UNCOMMITTED")
    assert not lu.is_disallowed("READ COMMITTED")
    assert lu.is_disallowed("REPEATABLE READ")
    assert lu.is_disallowed("SERIALIZABLE")

    dw = get_pattern("C-DW")
    assert dw.is_disallowed("READ UNCOMMITTED")
    assert dw.is_disallowed("SERIALIZABLE")


# =====================================================================
# 2. Schema & Statement Generator Tests
# =====================================================================
def test_schema_generator_synthetic_columns():
    gen = SchemaGenerator(seed=123)
    db = gen.generate_benchmark_schema()
    assert "t1" in db.tables
    assert "t2" in db.tables
    
    # Verify synthetic columns per Section 3.2.1
    t1 = db.tables["t1"]
    assert "row_id" in t1.col_map
    assert "version" in t1.col_map
    assert t1.pk_column.name == "row_id"

    # Verify foreign key candidate matching
    t2 = db.tables["t2"]
    assert t2.col_map["t1_ref"].fk_ref == ("t1", "row_id")


def test_seed_data_referential_integrity():
    gen = SchemaGenerator(seed=42)
    db = gen.generate_benchmark_schema()
    inserts = gen.generate_seed_data(db, rows_per_table=5)
    assert len(inserts) == 10
    assert len(db.inserted_pks["t1"]) == 5
    assert len(db.inserted_pks["t2"]) == 5


def test_join_query_synthesis():
    gen = SchemaGenerator()
    db = gen.generate_benchmark_schema()
    for jtype in ("INNER", "LEFT", "RIGHT", "CROSS"):
        sql = gen.generate_join_query(db, jtype)
        assert jtype in sql or "JOIN" in sql


# =====================================================================
# 3. Algorithm 1: Transaction Generator Tests
# =====================================================================
def test_algorithm_1_transaction_generation():
    db = SchemaGenerator().generate_benchmark_schema()
    tg = TransactionGenerator(db)
    pattern = get_pattern("C-LU")
    case = tg.generate(pattern, isolation_level="REPEATABLE READ")

    assert case.pattern.pattern_id == "C-LU"
    assert len(case.txn_statements[1]) == 3  # R, W, C
    assert len(case.txn_statements[2]) == 2  # W, C
    assert len(case.global_schedule) == 5

    # Check condition alignment: WHERE row_id = 1
    assert "WHERE row_id = 1" in case.global_schedule[0]["sql"]
    assert "WHERE row_id = 1" in case.global_schedule[1]["sql"]


# =====================================================================
# 4. Algorithm 2 & Execution Coordinator Tests
# =====================================================================
def test_execution_engine_sqlite_testbed():
    engine = ExecutionEngine()
    conn = engine.create_in_memory_testbed()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM t1;")
    assert cur.fetchone()[0] == 3

    # Trigger test
    cur.execute("UPDATE t1 SET c0 = 999 WHERE row_id = 1;")
    conn.commit()
    cur.execute("SELECT operation_type, row_id, new_c0 FROM t1_log WHERE operation_type = 'UPDATE';")
    log_row = cur.fetchone()
    assert log_row[0] == "UPDATE"
    assert log_row[1] == 1
    assert log_row[2] == 999


def test_execution_trace_wal_observer():
    db = SchemaGenerator().generate_benchmark_schema()
    tg = TransactionGenerator(db)
    engine = ExecutionEngine()
    
    case = tg.generate(get_pattern("C-LU"))
    trace = engine.execute_test_case(case)
    
    assert len(trace.steps) == 5
    assert len(trace.wal_observer_log) == 2  # 2 write operations recorded
    assert trace.final_state["t1"][0]["c0"] == 1100  # Final write by T1


# =====================================================================
# 5. Dynamic Dependency Graph & Two-Phase Detector Tests
# =====================================================================
def test_dependency_graph_edges():
    g = DependencyGraph()
    e1 = DependencyEdge("ww", 1, 2, 1, 2, 500)
    e2 = DependencyEdge("rw", 2, 1, 1, 3, 1100)
    g.add_edge(e1)
    g.add_edge(e2)

    assert g.has_edge("ww", 1, 2)
    assert g.has_edge("rw", 2, 1)
    assert g.has_cycle()  # T1 -> T2 and T2 -> T1


def test_two_phase_detector_explicit_error_filtering():
    detector = TwoPhaseDetector()
    db = SchemaGenerator().generate_benchmark_schema()
    tg = TransactionGenerator(db)
    case = tg.generate(get_pattern("C-LU"), isolation_level="REPEATABLE READ")
    trace = ExecutionTrace(case)
    
    # Step with expected deadlock should be filtered out (not treated as isolation bug)
    from aptrans.execution_engine import ExecutionStepResult
    step_res = ExecutionStepResult(1, 1, "R1[x0]", case.global_schedule[0]["sql"])
    step_res.error_message = "Deadlock found when trying to get lock; try restarting transaction"
    trace.steps.append(step_res)

    report = detector.detect(trace)
    assert not report.phase1_explicit_bug
    assert len(report.filtered_errors) == 1
    assert "Expected Deadlock" in report.filtered_errors[0]


# =====================================================================
# 6. Real-World Case Studies Tests
# =====================================================================
def test_case_study_1_mysql_dirty_read():
    res = CaseStudyReplayer.run_case_study_1_mysql()
    assert res["bug_id"] == "MySQL Bug #117835"
    assert res["report"]["verdict"] == "BUG_IMPLICIT"
    assert res["report"]["is_bug"] is True
    assert "Dirty Read" in res["report"]["matched_anomaly_pattern"]


def test_case_study_2_oceanbase_non_repeatable_read():
    res = CaseStudyReplayer.run_case_study_2_oceanbase()
    assert res["bug_id"] == "OceanBase Bug #2248"
    assert res["report"]["verdict"] == "BUG_IMPLICIT"
    assert res["report"]["is_bug"] is True
    assert "Non-Repeatable Read" in res["anomaly_name"]


def test_case_study_3_mariadb_autoinc_serialization():
    res = CaseStudyReplayer.run_case_study_3_mariadb()
    assert res["bug_id"] == "MariaDB Bug #36330"
    assert res["report"]["verdict"] == "BUG_IMPLICIT"
    assert res["report"]["is_bug"] is True
    assert "Serialization" in res["anomaly_name"]


# =====================================================================
# 7. Benchmark Replay Data Integrity
# =====================================================================
def test_benchmark_data_integrity():
    data = get_benchmark_data()
    assert len(data["table_5_bugs"]) == 13
    assert data["table_6_comparison"]["APTrans"]["total_true_positives"] == 72
    assert len(data["table_7_ablation"]) == 3


# =====================================================================
# 8. REST API Tests
# =====================================================================
@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_api_patterns(client):
    res = client.get("/api/aptrans/patterns")
    assert res.status_code == 200
    assert res.json["total_patterns"] == 46


def test_api_generate_and_execute(client):
    payload = {"pattern_id": "C-LU", "isolation_level": "REPEATABLE READ"}
    res = client.post("/api/aptrans/execute", json=payload)
    assert res.status_code == 200
    assert "trace" in res.json
    assert "report" in res.json


def test_api_case_studies(client):
    for cs in (1, 2, 3):
        res = client.get(f"/api/aptrans/case-studies/{cs}")
        assert res.status_code == 200
        assert res.json["report"]["is_bug"] is True


def test_api_evaluation(client):
    res = client.get("/api/aptrans/evaluation")
    assert res.status_code == 200
    assert res.json["normalized_score"] >= 9.0
