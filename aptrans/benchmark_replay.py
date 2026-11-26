"""
APTrans Empirical Benchmark & Ablation Replay Engine
Paper: "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026, Section 4.2 - 4.4)

Replicates and serves the experimental evaluations:
- Table 5: 13 Transaction Bugs detected by APTrans across MySQL, MariaDB, OceanBase, OpenGauss
- Table 6: 72-Hour Comparison of Bug-Finding Capabilities (APTrans vs TxCheck vs Troc)
- Table 7: 24-Hour Ablation Study (APTrans vs APTrans-Pattern vs APTrans-ImplicitChecker)
"""

from typing import Dict, List, Any

# =====================================================================
# Table 5: Bugs Detected by APTrans
# =====================================================================
TABLE_5_BUGS: List[Dict[str, Any]] = [
    {
        "dbms": "MySQL",
        "bug_id": "115978",
        "status": "Duplicate",
        "severity": "Moderate",
        "isolation_level": "SERIALIZABLE",
        "oracle": "Implicit",
        "pattern": "P34",
        "summary": "Serializable isolation violation under secondary index range scans"
    },
    {
        "dbms": "MySQL",
        "bug_id": "117218",
        "status": "Confirm",
        "severity": "Moderate",
        "isolation_level": "REPEATABLE READ",
        "oracle": "Implicit",
        "pattern": "P2",
        "summary": "Non-repeatable read when combining consistent reads with locking updates"
    },
    {
        "dbms": "MySQL",
        "bug_id": "117733",
        "status": "Confirm",
        "severity": "Serious",
        "isolation_level": "READ COMMITTED",
        "oracle": "Implicit",
        "pattern": "P1",
        "summary": "Semi-consistent read observing uncommitted secondary index record"
    },
    {
        "dbms": "MySQL",
        "bug_id": "117835",
        "status": "Confirm",
        "severity": "Critical",
        "isolation_level": "READ COMMITTED",
        "oracle": "Implicit",
        "pattern": "C-DR",
        "summary": "Dirty read where reader observes uncommitted value 0 that subsequently rolls back"
    },
    {
        "dbms": "MySQL",
        "bug_id": "117860",
        "status": "Confirm",
        "severity": "Serious",
        "isolation_level": "SERIALIZABLE",
        "oracle": "Implicit",
        "pattern": "P37",
        "summary": "Write skew anomaly allowed under serializable due to missing predicate lock"
    },
    {
        "dbms": "MariaDB",
        "bug_id": "35335",
        "status": "Confirm",
        "severity": "Critical",
        "isolation_level": "SERIALIZABLE",
        "oracle": "Implicit",
        "pattern": "P39",
        "summary": "Aria storage engine concurrent cross-update isolation failure"
    },
    {
        "dbms": "MariaDB",
        "bug_id": "35464",
        "status": "Confirm",
        "severity": "Critical",
        "isolation_level": "REPEATABLE READ",
        "oracle": "Implicit",
        "pattern": "C-LU",
        "summary": "Lost update when optimistic record lock flag is cleared prematurely"
    },
    {
        "dbms": "MariaDB",
        "bug_id": "36120",
        "status": "Inconsistency",
        "severity": "Serious",
        "isolation_level": "ALL",
        "oracle": "Implicit",
        "pattern": "P4",
        "summary": "Dirty write cycle across multi-table foreign key cascade triggers"
    },
    {
        "dbms": "MariaDB",
        "bug_id": "36308",
        "status": "Inconsistency",
        "severity": "Critical",
        "isolation_level": "REPEATABLE READ",
        "oracle": "Implicit",
        "pattern": "P30",
        "summary": "Snapshot view corruption following multi-statement table reorganization"
    },
    {
        "dbms": "MariaDB",
        "bug_id": "36330",
        "status": "Confirm",
        "severity": "Critical",
        "isolation_level": "SERIALIZABLE",
        "oracle": "Implicit",
        "pattern": "P36",
        "summary": "Auto-increment primary key interleaving producing non-serializable 3-row view"
    },
    {
        "dbms": "OceanBase",
        "bug_id": "2248",
        "status": "Confirm",
        "severity": "High",
        "isolation_level": "REPEATABLE READ",
        "oracle": "Implicit",
        "pattern": "P3",
        "summary": "Consistent snapshot bypass: reader observes committed writes after snapshot taken"
    },
    {
        "dbms": "OceanBase",
        "bug_id": "2419",
        "status": "Confirm",
        "severity": "Serious",
        "isolation_level": "SERIALIZABLE",
        "oracle": "Implicit",
        "pattern": "C-WS",
        "summary": "Write skew permitted under Serializable due to snapshot isolation engine mapping"
    },
    {
        "dbms": "OpenGauss",
        "bug_id": "IBZAAG",
        "status": "Confirm",
        "severity": "High",
        "isolation_level": "ALL",
        "oracle": "Explicit",
        "pattern": "Crash",
        "summary": "Assertion failure in lock manager during concurrent 2PL lock upgrade"
    }
]

# =====================================================================
# Table 6: Comparison of Bug-Finding Capabilities in 72 Hours
# =====================================================================
TABLE_6_COMPARISON = {
    "APTrans": {
        "MySQL": {"total": 25, "true_positive": 25, "false_positive": 0, "precision": 100.0},
        "MariaDB": {"total": 23, "true_positive": 23, "false_positive": 0, "precision": 100.0},
        "OceanBase": {"total": 24, "true_positive": 24, "false_positive": 0, "precision": 100.0},
        "total_true_positives": 72
    },
    "TxCheck": {
        "MySQL": {"total": 24, "true_positive": 0, "false_positive": 24, "precision": 0.0},
        "MariaDB": {"total": 73, "true_positive": 0, "false_positive": 73, "precision": 0.0},
        "OceanBase": {"total": "N/A", "true_positive": "N/A", "false_positive": "N/A", "precision": "N/A"},
        "reasons_for_fp": [
            "Unable to handle cyclic dependencies in dynamic scheduling (46 cases)",
            "Incorrect dependency order analysis in complex subqueries (35 cases)",
            "Syntax / semantic errors in random SQL statements (16 cases)"
        ]
    },
    "Troc": {
        "MySQL": {"total": 23, "true_positive": 0, "false_positive": 23, "precision": 0.0},
        "MariaDB": {"total": 18, "true_positive": 0, "false_positive": 18, "precision": 0.0},
        "OceanBase": {"total": 39, "true_positive": 0, "false_positive": 39, "precision": 0.0},
        "reasons_for_fp": [
            "Snapshot creation timing mismatch between view and RDBMS (41 cases)",
            "Lock wait timeout differences (15 cases)",
            "Incorrect isolation interpretation (assuming RR prevents phantoms) (16 cases)",
            "Result comparison list vs bag comparison discrepancy (8 cases)"
        ]
    }
}

# =====================================================================
# Table 7: Ablation Experiment Results (24 Hours)
# =====================================================================
TABLE_7_ABLATION = [
    {
        "method": "APTrans (Full Framework)",
        "mysql": 9,
        "mariadb": 3,
        "oceanbase": 4,
        "total": 16,
        "description": "Full anomaly pattern guidance + two-phase detection"
    },
    {
        "method": "APTrans-Pattern (Random Generation)",
        "mysql": 4,
        "mariadb": 2,
        "oceanbase": 2,
        "total": 8,
        "description": "Replaces pattern-guided generation with randomized transactions (50% drop in bug triggering)"
    },
    {
        "method": "APTrans-Implicit Checker (Explicit Only)",
        "mysql": 0,
        "mariadb": 0,
        "oceanbase": 0,
        "total": 0,
        "description": "Removes implicit dependency graph checking (0 bugs found; proves all bugs are silent!)"
    }
]

def get_benchmark_data() -> Dict[str, Any]:
    return {
        "table_5_bugs": TABLE_5_BUGS,
        "table_6_comparison": TABLE_6_COMPARISON,
        "table_7_ablation": TABLE_7_ABLATION
    }
