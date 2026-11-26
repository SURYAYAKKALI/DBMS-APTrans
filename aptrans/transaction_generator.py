"""
APTrans Transaction Generator (Algorithm 1)
Paper: "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026, Section 3.3)

Implements:
- Statement Selection based on Statement Type Constraints (Cstr1)
- Condition Alignment based on Data Access Constraints (Cstr2)
  * Mapping abstract variables (x, y) to concrete row IDs (e.g., row_id = 1, row_id = 2)
  * Updating WHERE clauses to target shared or conflicting records
- Transaction Composition based on Schedule Order Constraints (Cstr3)
- Transaction Packaging: prepending isolation level commands and BEGIN/START TRANSACTION
"""

import copy
from typing import Dict, List, Tuple, Any, Optional
from .patterns import AnomalyPattern, Operation
from .schema_generator import DatabaseSchema

class TransactionCase:
    """Represents a fully composed concurrent test case ready for scheduled execution."""
    def __init__(self, pattern: AnomalyPattern, isolation_level: str = "REPEATABLE READ", use_consistent_snapshot: bool = False):
        self.pattern = pattern
        self.isolation_level = isolation_level.upper()
        self.use_consistent_snapshot = use_consistent_snapshot
        
        # Raw statement lists per transaction (e.g. {1: [stmt1, stmt2], 2: [stmt1, stmt2]})
        self.txn_statements: Dict[int, List[Dict[str, Any]]] = {1: [], 2: []}
        
        # Interleaved global schedule sequence of statements according to Cstr3
        self.global_schedule: List[Dict[str, Any]] = []

    def get_sql_script(self) -> str:
        """Returns human-readable SQL representation of the test case."""
        lines = [
            f"-- ================================================================",
            f"-- APTrans Test Case Guided by Pattern: {self.pattern.pattern_id} ({self.pattern.name})",
            f"-- Raw Pattern: {self.pattern.raw_pattern}",
            f"-- Target Isolation Level: {self.isolation_level}",
            f"-- Disallowed In: {', '.join(self.pattern.disallowed_levels)}",
            f"-- ================================================================\n"
        ]
        
        # Print transaction definitions
        for txnid in (1, 2):
            lines.append(f"-- ----------------- Transaction {txnid} -----------------")
            if self.use_consistent_snapshot:
                lines.append(f"/* txn {txnid} */ SET TRANSACTION ISOLATION LEVEL {self.isolation_level};")
                lines.append(f"/* txn {txnid} */ START TRANSACTION WITH CONSISTENT SNAPSHOT;")
            else:
                lines.append(f"/* txn {txnid} */ SET TRANSACTION ISOLATION LEVEL {self.isolation_level};")
                lines.append(f"/* txn {txnid} */ BEGIN;")
            for s in self.txn_statements[txnid]:
                lines.append(f"/* txn {txnid} */ {s['sql']}")
            lines.append("")

        lines.append("-- ----------------- Interleaved Schedule (Algorithm 2) -----------------")
        for step_idx, step in enumerate(self.global_schedule, start=1):
            lines.append(f"Step {step_idx:02d} | Txn {step['txn_id']} | {step['notation']:<10} | {step['sql']}")
            
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern.pattern_id,
            "pattern_name": self.pattern.name,
            "raw_pattern": self.pattern.raw_pattern,
            "isolation_level": self.isolation_level,
            "use_consistent_snapshot": self.use_consistent_snapshot,
            "disallowed_levels": self.pattern.disallowed_levels,
            "txn_statements": self.txn_statements,
            "global_schedule": self.global_schedule,
            "sql_script": self.get_sql_script()
        }


class TransactionGenerator:
    """
    Implements Algorithm 1 (Transaction Generation) from Section 3.3.2.
    """
    def __init__(self, db_schema: DatabaseSchema):
        self.db_schema = db_schema
        # Variable mapping: x -> row_id 1, y -> row_id 2
        self.var_to_row_id: Dict[str, int] = {
            "x": 1,
            "y": 2
        }

    def generate(self, pattern: AnomalyPattern, isolation_level: str = "REPEATABLE READ", 
                 use_consistent_snapshot: bool = False, custom_values: Optional[Dict[str, int]] = None) -> TransactionCase:
        """
        Executes Algorithm 1:
        1. Statement Selection (Lines 2-4)
        2. Condition Alignment (Lines 5-13)
        3. Transaction Composition & Packaging (Lines 14-19)
        """
        case = TransactionCase(pattern, isolation_level, use_consistent_snapshot)
        
        # Candidate value offsets for writes:
        # e.g. x1 = 500, x2 = 1100, y1 = 700, y2 = 1400
        val_map = {
            "x0": 100, "x1": 500, "x2": 1100,
            "y0": 200, "y1": 700, "y2": 1400
        }
        if custom_values:
            val_map.update(custom_values)

        # Step 1: Pre-generate statements for each operation in pattern
        # AlignStmts[txnid] = list of statements for this transaction
        align_stmts: Dict[int, List[Dict[str, Any]]] = {1: [], 2: []}
        
        for op in pattern.operations:
            txnid = op.txn_id
            var = op.var_name
            ver = op.version
            var_key = f"{var}{ver}" if var else ""
            row_id = self.var_to_row_id.get(var, 1)

            stmt_dict: Dict[str, Any] = {
                "step_index": op.step_index,
                "txn_id": txnid,
                "op_type": op.op_type,
                "var_name": var,
                "version": ver,
                "row_id": row_id if var else None,
                "notation": str(op),
                "sql": ""
            }

            if op.op_type == 'R':
                # Read operation: SELECT row_id, version, c0 FROM t1 WHERE row_id = {row_id}
                stmt_dict["sql"] = f"SELECT row_id, version, c0, c1 FROM t1 WHERE row_id = {row_id};"
                stmt_dict["table"] = "t1"
            elif op.op_type == 'W':
                # Write operation: UPDATE t1 SET c0 = {val}, version = version + 1 WHERE row_id = {row_id}
                new_val = val_map.get(var_key, 999)
                stmt_dict["sql"] = f"UPDATE t1 SET c0 = {new_val}, version = version + 1 WHERE row_id = {row_id};"
                stmt_dict["written_value"] = new_val
                stmt_dict["table"] = "t1"
            elif op.op_type == 'C':
                stmt_dict["sql"] = "COMMIT;"
            elif op.op_type in ('A', 'B'):
                stmt_dict["sql"] = "ROLLBACK;"

            align_stmts[txnid].append(stmt_dict)

        # Store the transaction statements list
        case.txn_statements = copy.deepcopy(align_stmts)

        # Step 2: Transaction Composition (Lines 14-18)
        # Sequence through Cstr3 to assemble the interleaved global execution schedule
        queue_copy: Dict[int, List[Dict[str, Any]]] = {
            1: list(align_stmts[1]),
            2: list(align_stmts[2])
        }
        
        for step_txnid in pattern.cstr3:
            if queue_copy[step_txnid]:
                next_stmt = queue_copy[step_txnid].pop(0)
                case.global_schedule.append(next_stmt)

        return case
