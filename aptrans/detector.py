"""
APTrans Two-Phase Bug Detector & Dynamic Dependency Graph Engine
Paper: "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026, Section 3.5)

Implements:
- Phase 1: Explicit Error Capturing (crashes, assertion failures; filtering syntax/deadlock errors)
- Phase 2: Implicit Error Capturing:
  * Dynamic Dependency Graph G = (N, E) construction
  * ww (write-write) dependency inference on shared row_id
  * rw (read-write) anti-dependency inference
  * wr (write-read) version-aware dependency inference
  * Dependency cycle & path matching for target anomaly pattern
  * Isolation Level Violation Oracle (prohibitions per Table 1, Table 2, Table 3)
"""

from typing import Dict, List, Tuple, Any, Optional
from .patterns import AnomalyPattern
from .execution_engine import ExecutionTrace

class DependencyEdge:
    """Represents a directed dependency edge in G = (N, E)."""
    def __init__(self, dep_type: str, from_txn: int, to_txn: int, row_id: int, 
                 version: int, value: Any, detail: str = ""):
        self.dep_type = dep_type.lower()  # 'ww', 'wr', 'rw'
        self.from_txn = from_txn
        self.to_txn = to_txn
        self.row_id = row_id
        self.version = version
        self.value = value
        self.detail = detail

    def __repr__(self):
        return f"T{self.from_txn} --({self.dep_type}[row:{self.row_id}, v:{self.version}])--> T{self.to_txn}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.dep_type,
            "from_txn": self.from_txn,
            "to_txn": self.to_txn,
            "row_id": self.row_id,
            "version": self.version,
            "value": self.value,
            "detail": self.detail,
            "label": str(self)
        }


class DependencyGraph:
    """Dynamic Dependency Graph G = (N, E) built from transaction execution traces."""
    def __init__(self):
        self.nodes: List[int] = [1, 2]
        self.edges: List[DependencyEdge] = []

    def add_edge(self, edge: DependencyEdge):
        # Prevent duplicate identical edges
        for existing in self.edges:
            if (existing.dep_type == edge.dep_type and 
                existing.from_txn == edge.from_txn and 
                existing.to_txn == edge.to_txn and 
                existing.row_id == edge.row_id and 
                existing.version == edge.version):
                return
        self.edges.append(edge)

    def has_edge(self, dep_type: str, from_txn: int, to_txn: int) -> bool:
        return any(e.dep_type == dep_type.lower() and e.from_txn == from_txn and e.to_txn == to_txn for e in self.edges)

    def has_cycle(self) -> bool:
        """Checks for direct 2-transaction dependency cycles (T1 -> T2 and T2 -> T1)."""
        t1_to_t2 = any(e.from_txn == 1 and e.to_txn == 2 for e in self.edges)
        t2_to_t1 = any(e.from_txn == 2 and e.to_txn == 1 for e in self.edges)
        return t1_to_t2 and t2_to_t1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [{"id": n, "label": f"Txn {n}"} for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "has_cycle": self.has_cycle()
        }


class DetectionReport:
    """Consolidated report from the Two-Phase Bug Detector."""
    def __init__(self, pattern: AnomalyPattern, isolation_level: str):
        self.pattern = pattern
        self.isolation_level = isolation_level
        self.phase1_explicit_bug: bool = False
        self.phase1_details: List[str] = []
        self.filtered_errors: List[str] = []  # Syntax / deadlocks filtered out
        self.phase2_implicit_bug: bool = False
        self.matched_anomaly_pattern: Optional[str] = None
        self.anomaly_details: str = ""
        self.graph: DependencyGraph = DependencyGraph()
        self.is_bug: bool = False
        self.verdict: str = "PASS"  # 'BUG_EXPLICIT', 'BUG_IMPLICIT', 'PASS'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern.pattern_id,
            "pattern_name": self.pattern.name,
            "isolation_level": self.isolation_level,
            "is_bug": self.is_bug,
            "verdict": self.verdict,
            "phase1_explicit_bug": self.phase1_explicit_bug,
            "phase1_details": self.phase1_details,
            "filtered_errors": self.filtered_errors,
            "phase2_implicit_bug": self.phase2_implicit_bug,
            "matched_anomaly_pattern": self.matched_anomaly_pattern,
            "anomaly_details": self.anomaly_details,
            "graph": self.graph.to_dict()
        }


class TwoPhaseDetector:
    """
    Implements the two-phase transaction bug detection pipeline:
    - Phase 1: Explicit Error Capturing
    - Phase 2: Implicit Error Capturing via Dynamic Dependency Graph
    """
    def __init__(self):
        pass

    def detect(self, trace: ExecutionTrace) -> DetectionReport:
        case = trace.test_case
        pattern = case.pattern
        iso = case.isolation_level
        report = DetectionReport(pattern, iso)

        # =================================================================
        # Phase 1: Explicit Error Capturing (Section 3.5.1)
        # =================================================================
        # Check crashes and assertion failures
        if trace.crashes:
            report.phase1_explicit_bug = True
            report.phase1_details.extend([f"Server Crash: {c}" for c in trace.crashes])
        if trace.assertion_failures:
            report.phase1_explicit_bug = True
            report.phase1_details.extend([f"Assertion Failure: {a}" for a in trace.assertion_failures])

        # Inspect step error messages: filter deadlocks and syntax errors
        for step in trace.steps:
            if step.error_message:
                err = step.error_message.lower()
                if "deadlock" in err or "lock wait timeout" in err:
                    report.filtered_errors.append(f"Expected Deadlock/Timeout (Txn {step.txn_id}): {step.error_message}")
                elif "syntax" in err or "parse" in err:
                    report.filtered_errors.append(f"Syntax/Semantic Error (Txn {step.txn_id}): {step.error_message}")
                else:
                    report.phase1_explicit_bug = True
                    report.phase1_details.append(f"Explicit Internal DB Error (Txn {step.txn_id}): {step.error_message}")

        if report.phase1_explicit_bug:
            report.is_bug = True
            report.verdict = "BUG_EXPLICIT"
            return report

        # =================================================================
        # Phase 2: Implicit Error Capturing (Section 3.5.2)
        # Construct Dynamic Dependency Graph G = (N, E)
        # =================================================================
        g = DependencyGraph()
        
        # Collect write history (from WAL observer and trigger database_log)
        writes = []
        for entry in trace.wal_observer_log:
            writes.append({
                "txn_id": entry["txn_id"],
                "row_id": entry["row_id"],
                "version": entry["version"],
                "new_c0": entry["new_c0"],
                "status": entry.get("status", "COMMITTED")
            })

        # Collect read history from steps
        reads = []
        for step in trace.steps:
            if step.read_rows:
                for r in step.read_rows:
                    reads.append({
                        "step_idx": step.step_idx,
                        "txn_id": step.txn_id,
                        "row_id": r.get("row_id", 1),
                        "version": r.get("version"),
                        "c0": r.get("c0")
                    })

        # 1. Infer Write-Write (ww) Dependencies
        # If T1 writes row_id, then T2 writes row_id
        for i, w1 in enumerate(writes):
            for w2 in writes[i+1:]:
                if w1["row_id"] == w2["row_id"] and w1["txn_id"] != w2["txn_id"]:
                    g.add_edge(DependencyEdge(
                        dep_type="ww",
                        from_txn=w1["txn_id"],
                        to_txn=w2["txn_id"],
                        row_id=w1["row_id"],
                        version=w2["version"],
                        value=w2["new_c0"],
                        detail=f"T{w2['txn_id']} overwrote row {w1['row_id']} previously modified by T{w1['txn_id']}"
                    ))

        # 2. Infer Read-Write (rw) Anti-Dependencies
        # If T1 reads version xi of row, and T2 subsequently installs version xi+1 of row
        for r in reads:
            for w in writes:
                if r["row_id"] == w["row_id"] and r["txn_id"] != w["txn_id"]:
                    if w["version"] > (r["version"] or 0):
                        g.add_edge(DependencyEdge(
                            dep_type="rw",
                            from_txn=r["txn_id"],
                            to_txn=w["txn_id"],
                            row_id=r["row_id"],
                            version=w["version"],
                            value=w["new_c0"],
                            detail=f"T{w['txn_id']} modified row {r['row_id']} after T{r['txn_id']} read version {r['version']}"
                        ))

        # 3. Infer Write-Read (wr) Dependencies
        # If T1 writes row, and T2 reads that written version or uncommitted write
        for w in writes:
            for r in reads:
                if w["row_id"] == r["row_id"] and w["txn_id"] != r["txn_id"]:
                    # Case B: T1 was uncommitted and rolled back, but T2 read its uncommitted value (Dirty Read)
                    if w.get("status") == "ROLLED_BACK" and r["c0"] == w["new_c0"]:
                        g.add_edge(DependencyEdge(
                            dep_type="wr",
                            from_txn=w["txn_id"],
                            to_txn=r["txn_id"],
                            row_id=w["row_id"],
                            version=w["version"],
                            value=w["new_c0"],
                            detail=f"Dirty Read: T{r['txn_id']} observed dirty uncommitted write of rolled-back T{w['txn_id']}"
                        ))
                    # Case A: T2 read the committed version written by T1
                    elif r["c0"] == w["new_c0"] or (r["version"] is not None and r["version"] == w["version"]):
                        g.add_edge(DependencyEdge(
                            dep_type="wr",
                            from_txn=w["txn_id"],
                            to_txn=r["txn_id"],
                            row_id=w["row_id"],
                            version=w["version"],
                            value=w["new_c0"],
                            detail=f"T{r['txn_id']} observed write (v:{w['version']}, val:{w['new_c0']}) installed by T{w['txn_id']}"
                        ))

        report.graph = g

        # =================================================================
        # Pattern Matching & Isolation Violation Check
        # =================================================================
        # Match target anomaly pattern against dependency graph
        pid = pattern.pattern_id
        
        # A. Check Dirty Read
        if pid in ("C-DR", "P1") or "dirty read" in pattern.name.lower():
            # Requires wr edge where writer was rolled back or uncommitted
            has_dirty_wr = any(e.dep_type == "wr" and "dirty" in e.detail.lower() for e in g.edges)
            if has_dirty_wr and pattern.is_disallowed(iso):
                report.phase2_implicit_bug = True
                report.matched_anomaly_pattern = pattern.name
                report.anomaly_details = f"Dirty Read anomaly detected: T2 read uncommitted/rolled-back data under {iso}."

        # B. Check Lost Update
        elif pid in ("C-LU", "P28", "P30") or "lost update" in pattern.name.lower():
            # Requires rw edge T1 -> T2 and ww edge T2 -> T1 (cycle)
            has_rw_1_2 = g.has_edge("rw", 1, 2)
            has_ww_2_1 = g.has_edge("ww", 2, 1)
            if (has_rw_1_2 and has_ww_2_1) or (g.has_cycle() and pattern.is_disallowed(iso)):
                report.phase2_implicit_bug = True
                report.matched_anomaly_pattern = pattern.name
                report.anomaly_details = f"Lost Update anomaly detected: T1 overwrote committed update of T2 without seeing it under {iso}."

        # C. Check Non-Repeatable Read / Consistent Snapshot Violations
        elif pid in ("C-NRR", "P2", "P3", "P27") or "non-repeatable" in pattern.name.lower():
            # Under RR/SER, observing a concurrent transaction's write committed after snapshot is a violation
            has_wr = any(e.dep_type == "wr" for e in g.edges)
            if has_wr and pattern.is_disallowed(iso):
                report.phase2_implicit_bug = True
                report.matched_anomaly_pattern = pattern.name
                report.anomaly_details = f"Non-Repeatable Read anomaly detected: reader observed modification committed after snapshot under {iso}."

        # D. Check Write Skew / Read Skew / Serialization Cycles
        elif pid in ("C-WS", "C-RS", "P34", "P36", "P37", "P38", "P39", "P40") or "Skew" in pattern.name:
            if g.has_cycle() and pattern.is_disallowed(iso):
                report.phase2_implicit_bug = True
                report.matched_anomaly_pattern = pattern.name
                report.anomaly_details = f"Serialization graph cycle detected ({[str(e) for e in g.edges]}) under {iso}."

        # General pattern matching: If graph exhibits cyclic dependency or disallowed pattern matches
        if not report.phase2_implicit_bug and g.has_cycle() and pattern.is_disallowed(iso):
            report.phase2_implicit_bug = True
            report.matched_anomaly_pattern = pattern.name
            report.anomaly_details = f"Disallowed transaction dependency cycle matched under {iso}."

        if report.phase2_implicit_bug:
            report.is_bug = True
            report.verdict = "BUG_IMPLICIT"
        else:
            report.is_bug = False
            report.verdict = "PASS"

        return report
