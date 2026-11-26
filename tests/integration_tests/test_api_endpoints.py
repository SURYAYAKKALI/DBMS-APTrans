"""
End-to-End API Route Tests for TransactionGuard
Validates all endpoints specified in Section 13 & 22 of the proposal.
"""

import pytest
from database.connection import db_manager
from backend.main import health_check
from backend.api.routes import projects, runs, anomalies, rules, metrics, demo
from backend.api.schemas.models import ProjectCreate, ConnectionTestRequest, RunCreate, RuleCreate

@pytest.fixture(autouse=True)
def setup_db():
    db_manager.init_database()

def test_health():
    res = health_check()
    assert res["status"] == "HEALTHY"
    assert "service" in res

def test_projects_crud():
    # 1. List projects
    projs = projects.list_projects()
    assert len(projs) >= 1

    # 2. Create project
    created = projects.create_project(ProjectCreate(
        name="Integration Project",
        description="Pytest verification",
        database_config='{"engine": "sqlite"}'
    ))
    assert created["project_id"].startswith("PROJ-")
    assert created["name"] == "Integration Project"

def test_connection_test():
    res = projects.test_connection(ConnectionTestRequest(engine_type="sqlite"))
    assert res["success"] is True

def test_run_creation_and_execution():
    # 1. Create run
    run_info = runs.create_run(RunCreate(
        project_id="PROJ-DEFAULT",
        isolation_level="READ COMMITTED",
        workload_type="lost_update",
        concurrency=2,
        apply_mitigation=False
    ))
    run_id = run_info["run_id"]
    assert run_id.startswith("RUN-")

    # 2. Execute run
    exec_summary = runs.execute_run(run_id)
    assert exec_summary["status"] == "COMPLETED"
    assert exec_summary["total_txns"] == 2
    assert exec_summary["anomalies_detected"] >= 1

    # 3. Retrieve transactions & timeline
    tx_data = runs.get_run_transactions(run_id)
    assert tx_data["total_events"] > 0
    assert len(tx_data["transactions"]) == 2

    # 4. Retrieve dependencies & React Flow graph
    dep_data = runs.get_run_dependencies(run_id)
    assert len(dep_data["edges"]) > 0
    assert "react_flow" in dep_data

    # 5. Retrieve detected anomalies
    anom_list = runs.get_run_anomalies(run_id)
    assert len(anom_list) >= 1
    first_anom_id = anom_list[0]["anomaly_id"]

    # 6. Retrieve investigation detail
    inv_detail = anomalies.get_anomaly_detail(first_anom_id)
    assert "remediation_guide" in inv_detail
    assert "sql_code" in inv_detail["remediation_guide"]

    # 7. Retrieve metrics
    met_data = runs.get_run_metrics(run_id)
    assert met_data["total_transactions"] == 2
    assert met_data["throughput_tps"] > 0

    # 8. Retrieve full report
    rep_data = runs.get_run_report(run_id)
    assert rep_data["run_id"] == run_id
    assert "executive_summary" in rep_data

def test_business_rules_management():
    # List rules
    rule_list = rules.get_rules()
    assert len(rule_list) >= 4  # Standard invariants

    # Add custom rule
    new_rule = rules.create_rule(RuleCreate(
        name="Custom Non-Zero Price Rule",
        target_table="orders",
        rule_definition="total_amount > 0",
        severity="MEDIUM"
    ))
    assert new_rule["rule_id"].startswith("RULE-")

def test_performance_analytics_endpoints():
    kpis = metrics.get_overview_kpis()
    assert "total_test_runs" in kpis
    assert "total_anomalies_detected" in kpis

    comparison = metrics.get_benchmark_comparison(workload="lost_update", concurrency=2)
    assert len(comparison["benchmark_results"]) == 3  # Read Committed, Repeatable Read, Serializable

    workloads = metrics.get_workload_catalog()
    assert len(workloads) >= 5

def test_live_demo_endpoints():
    status = demo.get_last_item_status()
    assert status["equipment_id"] == "EQ-LAPTOP-01"

    # Vulnerable run (Lost update occurs)
    vuln = demo.run_last_item_demo(mitigation=False, isolation_level="READ COMMITTED")
    assert len(vuln["analysis"]["anomalies"]) > 0

    # Mitigated run (Correction prevents anomaly)
    mit = demo.run_last_item_demo(mitigation=True, isolation_level="SERIALIZABLE")
    assert mit["schedule_result"]["outcomes"]["TXN-02"] == "ABORTED"
    assert mit["final_inventory_quantity"] == 0  # Invariant preserved, only 1 unit sold!
