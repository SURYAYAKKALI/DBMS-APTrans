"""
System Metrics & Isolation Benchmark Analytics Endpoints
"""

from fastapi import APIRouter
from typing import Dict, Any
from database.connection import db_manager
from backend.analytics.benchmark_engine import benchmark_engine
from backend.core.workload_generator import WorkloadGenerator

router = APIRouter(prefix="/analytics", tags=["Performance & Benchmarking"])

@router.get("/overview")
def get_overview_kpis():
    conn = db_manager.get_raw_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(total_txns), SUM(committed_txns), SUM(aborted_txns), SUM(anomalies_detected) FROM test_runs")
    row = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM anomalies")
    total_anomalies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM business_rules WHERE enabled = 1")
    active_rules = cursor.fetchone()[0]
    conn.close()

    total_runs = row[0] or 0
    total_txns = row[1] or 0
    committed = row[2] or 0
    aborted = row[3] or 0

    return {
        "total_test_runs": total_runs,
        "total_transactions": total_txns,
        "committed_transactions": committed,
        "aborted_transactions": aborted,
        "success_rate_pct": round((committed / total_txns * 100.0) if total_txns > 0 else 100.0, 1),
        "total_anomalies_detected": total_anomalies,
        "active_business_rules": active_rules,
        "database_consistency_status": "MONITORED" if total_anomalies == 0 else "ANOMALIES_PRESENT"
    }

@router.get("/benchmark-comparison")
def get_benchmark_comparison(workload: str = "lost_update", concurrency: int = 5):
    return benchmark_engine.run_isolation_comparison(workload, concurrency)

@router.get("/scalability-sweep")
def get_scalability_sweep():
    return benchmark_engine.run_scalability_sweep()

@router.get("/workloads")
def get_workload_catalog():
    return WorkloadGenerator.get_supported_workloads()
