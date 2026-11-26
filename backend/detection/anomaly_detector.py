"""
TransactionGuard Core Anomaly Detector
Implements the 4-stage Two-Phase Anomaly Detection Algorithm described in Section 10 of the proposal:
1. Execution history reconstruction
2. Dependency extraction (WR, RW, WW)
3. Graph construction and pattern matching
4. Isolation and invariant validation
"""

import uuid
import json
from typing import Dict, Any, List

from database.connection import db_manager
from backend.core.event_collector import event_collector
from backend.detection.history_reconstruction import HistoryReconstructor
from backend.detection.dependency_builder import DependencyBuilder
from backend.detection.pattern_matcher import PatternMatcher
from backend.detection.isolation_validator import IsolationValidator
from backend.consistency.invariant_engine import invariant_engine

class AnomalyDetector:
    @staticmethod
    def analyze_run(run_id: str, isolation_level: str = "READ COMMITTED") -> Dict[str, Any]:
        events = event_collector.get_run_events(run_id)
        txns = event_collector.get_run_transactions(run_id)

        # Stage 1: History Reconstruction
        histories = HistoryReconstructor.reconstruct(events, txns)

        # Stage 2 & 3: Dependency Graph & Cycles
        dep_info = DependencyBuilder.build_dependencies(histories, run_id)

        # Stage 3: Match Anomaly Patterns
        raw_candidates = PatternMatcher.match_patterns(histories, dep_info)

        # Stage 4: Validate against Isolation Level Rules
        verified_anomalies = []
        for cand in raw_candidates:
            validated = IsolationValidator.validate_anomaly(cand, isolation_level)
            validated["anomaly_id"] = f"ANOM-{uuid.uuid4().hex[:8].upper()}"
            validated["run_id"] = run_id
            verified_anomalies.append(validated)

        # Validate Business Invariants
        invariant_violations = invariant_engine.validate_all_invariants(run_id)
        for inv in invariant_violations:
            verified_anomalies.append({
                "anomaly_id": f"ANOM-{uuid.uuid4().hex[:8].upper()}",
                "run_id": run_id,
                "type": f"BUSINESS_INVARIANT_{inv['rule_id']}",
                "severity": inv["severity"],
                "involved_txns": list(histories.get("transactions", {}).keys()),
                "affected_records": [inv["target_table"]],
                "expected_behavior": f"System must satisfy rule: {inv['rule_name']}",
                "observed_behavior": inv["violation_details"],
                "evidence": f"Database state validation failed rule {inv['rule_name']}.",
                "suggested_fix": "Introduce atomic transaction constraints, check constraints, or SERIALIZABLE isolation.",
                "verdict": "BUSINESS_RULE_BREACH",
                "compliance_note": inv["violation_details"]
            })

        # Persist to database tables for historical audit
        conn = db_manager.get_raw_connection()
        cursor = conn.cursor()
        try:
            # Store dependencies
            for edge in dep_info.get("edges", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO dependencies 
                    (edge_id, run_id, source_txn, target_txn, dependency_type, table_name, row_id, details, is_cycle_member)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    edge["edge_id"], run_id, edge["source"], edge["target"],
                    edge["type"], edge["table"], edge["row_id"], edge["details"],
                    1 if edge.get("is_cycle_member") else 0
                ))

            # Store anomalies
            for anom in verified_anomalies:
                cursor.execute("""
                    INSERT OR REPLACE INTO anomalies
                    (anomaly_id, run_id, type, severity, involved_txns, affected_records, expected_behavior, observed_behavior, evidence, suggested_fix, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DETECTED')
                """, (
                    anom["anomaly_id"], run_id, anom["type"], anom["severity"],
                    json.dumps(anom.get("involved_txns", [])),
                    json.dumps(anom.get("affected_records", [])),
                    anom.get("expected_behavior", ""),
                    anom.get("observed_behavior", ""),
                    anom.get("evidence", ""),
                    anom.get("suggested_fix", "")
                ))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

        return {
            "run_id": run_id,
            "isolation_level": isolation_level,
            "total_events": len(events),
            "transactions_analyzed": len(txns),
            "dependencies": dep_info.get("edges", []),
            "cycles_detected": dep_info.get("cycles", []),
            "react_flow": dep_info.get("react_flow", {}),
            "anomalies": verified_anomalies,
            "invariant_violations": invariant_violations,
            "is_clean": len(verified_anomalies) == 0
        }

anomaly_detector = AnomalyDetector()
