"""
TransactionGuard Workload Generation Engine
Generates both controlled reproducible schedules and randomized stress workloads.
"""

from typing import Dict, Any, List

class WorkloadGenerator:
    @staticmethod
    def get_supported_workloads() -> List[Dict[str, Any]]:
        return [
            {
                "id": "lost_update",
                "name": "The Last Item Problem (Lost Update / Overselling)",
                "category": "Lost Update (P4)",
                "default_concurrency": 2,
                "description": "Two concurrent transactions attempt to purchase the last available laptop. Both read stock=1 and write stock=0.",
                "affected_table": "inventory",
                "target_records": ["INV-LAPTOP-01"]
            },
            {
                "id": "write_skew",
                "name": "Doctor-On-Duty / Equipment Overbooking (Write Skew)",
                "category": "Write Skew (A5B)",
                "default_concurrency": 2,
                "description": "Two concurrent transactions verify duty count >= 2. T1 takes Doc 1 off duty, T2 takes Doc 2 off duty. Both commit, leaving 0 on duty.",
                "affected_table": "doctors",
                "target_records": ["DOC-001", "DOC-002"]
            },
            {
                "id": "non_repeatable_read",
                "name": "Fuzzy Read / Non-Repeatable Read",
                "category": "Non-Repeatable Read (G1c)",
                "default_concurrency": 2,
                "description": "T1 reads inventory stock. T2 updates the stock and commits. T1 reads the same row again and observes inconsistent state.",
                "affected_table": "inventory",
                "target_records": ["INV-SERVER-01"]
            },
            {
                "id": "dirty_read",
                "name": "Uncommitted Read Rollback (Dirty Read)",
                "category": "Dirty Read (G1a/G1b)",
                "default_concurrency": 2,
                "description": "T1 updates a row without committing. T2 reads the uncommitted value. T1 then encounters an error and rolls back.",
                "affected_table": "inventory",
                "target_records": ["INV-PROJ-01"]
            },
            {
                "id": "read_skew",
                "name": "Snapshot Asymmetry (Read Skew)",
                "category": "Read Skew (A5A)",
                "default_concurrency": 2,
                "description": "T1 reads Account A. T2 transfers balance from Account B to Account A and commits. T1 reads Account B, observing broken balance invariant.",
                "affected_table": "equipment",
                "target_records": ["EQ-LAPTOP-01", "EQ-GPU-01"]
            },
            {
                "id": "stress_concurrency",
                "name": "High-Concurrency Multi-Session Stress Test",
                "category": "High Concurrency",
                "default_concurrency": 10,
                "description": "Rapid multi-threaded concurrent transactions executing randomized orders, reservations, and inventory updates.",
                "affected_table": "inventory",
                "target_records": ["ALL"]
            }
        ]
