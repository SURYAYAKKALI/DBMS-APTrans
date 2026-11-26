"""
Isolation Level Semantics Validator
Validates detected anomaly candidates against PostgreSQL formal isolation guarantees.
"""

from typing import Dict, Any, Tuple

# Matrix according to Section 9.7 of Proposal
ISOLATION_MATRIX = {
    "READ COMMITTED": {
        "DIRTY_READ": "PREVENTED",
        "NON_REPEATABLE_READ": "PERMITTED",
        "LOST_UPDATE": "PERMITTED_APPLICATION_BUG",
        "WRITE_SKEW": "PERMITTED",
        "DIRTY_WRITE": "PREVENTED",
        "READ_SKEW": "PERMITTED"
    },
    "REPEATABLE READ": {
        "DIRTY_READ": "PREVENTED",
        "NON_REPEATABLE_READ": "PREVENTED",
        "LOST_UPDATE": "PREVENTED_BY_DB",
        "WRITE_SKEW": "PERMITTED",  # PostgreSQL RR is Snapshot Isolation!
        "DIRTY_WRITE": "PREVENTED",
        "READ_SKEW": "PREVENTED"
    },
    "SERIALIZABLE": {
        "DIRTY_READ": "PREVENTED",
        "NON_REPEATABLE_READ": "PREVENTED",
        "LOST_UPDATE": "PREVENTED",
        "WRITE_SKEW": "PREVENTED",  # Prevented by SSI checks
        "DIRTY_WRITE": "PREVENTED",
        "READ_SKEW": "PREVENTED"
    }
}

class IsolationValidator:
    @staticmethod
    def validate_anomaly(anomaly: Dict[str, Any], isolation_level: str) -> Dict[str, Any]:
        """
        Determines whether the observed anomaly is:
        - ISOLATION_VIOLATION: Should be prevented by this isolation level, but occurred!
        - APPLICATION_CONCURRENCY_BUG: Permitted by DB isolation, but violates application correctness.
        - EXPECTED_BEHAVIOR: Normal behavior under weaker isolation levels.
        """
        iso_clean = isolation_level.upper()
        iso_rules = ISOLATION_MATRIX.get(iso_clean, ISOLATION_MATRIX["READ COMMITTED"])
        anomaly_type = anomaly.get("type", "UNKNOWN")
        expected_status = iso_rules.get(anomaly_type, "UNKNOWN")

        result = dict(anomaly)
        result["isolation_guarantee"] = expected_status

        if expected_status == "PREVENTED":
            result["verdict"] = "ISOLATION_VIOLATION"
            result["compliance_note"] = f"CRITICAL: {anomaly_type} was observed under {iso_clean}, violating engine guarantees!"
        elif expected_status == "PERMITTED_APPLICATION_BUG":
            result["verdict"] = "APPLICATION_CONCURRENCY_BUG"
            result["compliance_note"] = f"Application-level concurrency flaw: {anomaly_type} is possible in {iso_clean} when using non-atomic read-modify-write patterns."
        elif expected_status == "PERMITTED":
            result["verdict"] = "PERMITTED_BY_ISOLATION"
            result["compliance_note"] = f"{anomaly_type} is permitted by PostgreSQL under {iso_clean}. Upgrade to SERIALIZABLE or use explicit locking to avoid."
        else:
            result["verdict"] = "INVESTIGATION_FLAG"
            result["compliance_note"] = f"Anomaly detected under {iso_clean}."

        return result
