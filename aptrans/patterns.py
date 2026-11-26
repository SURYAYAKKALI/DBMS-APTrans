"""
APTrans Anomaly Pattern Formalism & Constraint Engine
Paper: "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026)

Implements:
- Formal Anomaly Pattern definitions (Definition 2.1)
- Table 2: 6 Canonical Anomaly Patterns (Dirty Write, Dirty Read, Lost Update, Non-Repeatable Read, Write Skew, Read Skew)
- Table 3: 40 Extended Anomaly Patterns (IDs 1-40) covering 2 transactions and 2 shared variables (x, y)
- Constraint Extractor:
  * Cstr1: Statement Type Constraints < (R, nR), (W, nW), (B, nB), (C, nC) >
  * Cstr2: Data Access Constraints DA: O -> V
  * Cstr3: Schedule Order Constraints [t1, t2, ..., tm]
- Adya Dependency Annotations (ww, wr, rw)
- Isolation Level Prohibition Matrix (RU, RC, RR, SER, ALL)
"""

import re
from typing import Dict, List, Tuple, Any, Optional

class Operation:
    """Represents a single atomic transactional operation within an anomaly pattern."""
    def __init__(self, op_type: str, txn_id: int, var_name: str, version: str, step_index: int):
        self.op_type = op_type.upper()      # 'R' (Read), 'W' (Write), 'C' (Commit), 'A'/'B' (Abort/Rollback)
        self.txn_id = int(txn_id)          # 1 or 2
        self.var_name = var_name            # 'x', 'y' or '' for commit/abort
        self.version = version              # e.g., '0', '1', '2'
        self.step_index = step_index        # In-schedule global position (0-indexed)

    def __repr__(self):
        if self.op_type in ('C', 'A', 'B'):
            return f"{self.op_type}{self.txn_id}"
        return f"{self.op_type}{self.txn_id}[{self.var_name}{self.version}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_type": self.op_type,
            "txn_id": self.txn_id,
            "var_name": self.var_name,
            "version": self.version,
            "step_index": self.step_index,
            "notation": str(self)
        }


class AnomalyPattern:
    """Represents a formalized anomaly pattern with extracted constraints and isolation rules."""
    def __init__(self, pattern_id: str, name: str, raw_pattern: str, disallowed_levels: List[str], description: str = ""):
        self.pattern_id = str(pattern_id)
        self.name = name
        self.raw_pattern = raw_pattern
        self.disallowed_levels = disallowed_levels  # e.g. ['ALL'], ['RC', 'RR', 'SER'], ['RR', 'SER'], ['SER']
        self.description = description
        
        # Parse into structured operations
        self.operations: List[Operation] = self._parse_pattern(raw_pattern)
        
        # Extract Cstr1, Cstr2, Cstr3 per Definitions 3.1, 3.2, 3.3
        self.cstr1: Dict[int, Dict[str, int]] = self._extract_cstr1()
        self.cstr2: List[Dict[str, Any]] = self._extract_cstr2()
        self.cstr3: List[int] = self._extract_cstr3()
        self.adya_dependencies: List[Dict[str, Any]] = self._infer_adya_dependencies()

    def _parse_pattern(self, pattern_str: str) -> List[Operation]:
        """
        Parses strings such as 'R1[x0] W2[x1] C2 W1[x2] C1' or 'W1[x1] R2[x1] A1 C2'
        using regex tokenization.
        """
        # Match tokens like R1[x0], W2[y1], C1, C2, A1, B1
        token_regex = re.compile(r'([RWACB])(\d)(?:\[([a-zA-Z])(\d+)\])?')
        ops = []
        step = 0
        for match in token_regex.finditer(pattern_str):
            op_type = match.group(1)
            txn_id = int(match.group(2))
            var_name = match.group(3) or ""
            version = match.group(4) or ""
            ops.append(Operation(op_type, txn_id, var_name, version, step))
            step += 1
        return ops

    def _extract_cstr1(self) -> Dict[int, Dict[str, int]]:
        """
        Definition 3.1: Statement Type Constraint
        For each transaction, four-tuple <(R, nR), (W, nW), (B, nB), (C, nC)>
        """
        cstr1: Dict[int, Dict[str, int]] = {
            1: {"R": 0, "W": 0, "B": 0, "C": 0},
            2: {"R": 0, "W": 0, "B": 0, "C": 0}
        }
        for op in self.operations:
            t = op.txn_id
            if t not in cstr1:
                cstr1[t] = {"R": 0, "W": 0, "B": 0, "C": 0}
            if op.op_type == 'R':
                cstr1[t]["R"] += 1
            elif op.op_type == 'W':
                cstr1[t]["W"] += 1
            elif op.op_type in ('A', 'B'):
                cstr1[t]["B"] += 1
            elif op.op_type == 'C':
                cstr1[t]["C"] += 1
        return cstr1

    def _extract_cstr2(self) -> List[Dict[str, Any]]:
        """
        Definition 3.2: Data Access Constraint DA: O -> V
        Establishes mapping between operation and shared data variables.
        """
        accesses = []
        txn_inner_counter: Dict[int, int] = {1: 0, 2: 0}
        for op in self.operations:
            if op.op_type in ('R', 'W'):
                txn_inner_counter[op.txn_id] += 1
                accesses.append({
                    "txn_id": op.txn_id,
                    "inner_idx": txn_inner_counter[op.txn_id],
                    "op_type": op.op_type,
                    "var_name": op.var_name,
                    "version": op.version,
                    "step_index": op.step_index,
                    "notation": f"{op.op_type}_{op.txn_id}^{txn_inner_counter[op.txn_id]} -> {op.var_name}{op.version}"
                })
        return accesses

    def _extract_cstr3(self) -> List[int]:
        """
        Definition 3.3: Schedule Order Constraint
        Sequence [t1, t2, ..., tm] regulating execution order of statements.
        """
        return [op.txn_id for op in self.operations]

    def _infer_adya_dependencies(self) -> List[Dict[str, Any]]:
        """
        Computes formal Adya dependencies (ww, wr, rw) embedded within this anomaly sequence.
        """
        deps = []
        data_ops = [op for op in self.operations if op.op_type in ('R', 'W')]
        for i, op1 in enumerate(data_ops):
            for op2 in data_ops[i+1:]:
                if op1.var_name == op2.var_name and op1.txn_id != op2.txn_id:
                    # Write-Write: Ti writes x, then Tj writes x
                    if op1.op_type == 'W' and op2.op_type == 'W':
                        deps.append({
                            "type": "ww",
                            "from_txn": op1.txn_id,
                            "to_txn": op2.txn_id,
                            "var": op1.var_name,
                            "desc": f"T{op2.txn_id} ww-depends on T{op1.txn_id} on {op1.var_name}"
                        })
                    # Write-Read: Ti writes x, then Tj reads x
                    elif op1.op_type == 'W' and op2.op_type == 'R':
                        deps.append({
                            "type": "wr",
                            "from_txn": op1.txn_id,
                            "to_txn": op2.txn_id,
                            "var": op1.var_name,
                            "desc": f"T{op2.txn_id} wr-depends on T{op1.txn_id} on {op1.var_name}"
                        })
                    # Read-Write: Ti reads x, then Tj writes x
                    elif op1.op_type == 'R' and op2.op_type == 'W':
                        deps.append({
                            "type": "rw",
                            "from_txn": op1.txn_id,
                            "to_txn": op2.txn_id,
                            "var": op1.var_name,
                            "desc": f"T{op2.txn_id} rw-depends on T{op1.txn_id} on {op1.var_name}"
                        })
        return deps

    def is_disallowed(self, isolation_level: str) -> bool:
        """Checks if this anomaly is prohibited under the specified isolation level."""
        iso_map = {
            "READ UNCOMMITTED": "RU",
            "READ COMMITTED": "RC",
            "REPEATABLE READ": "RR",
            "SERIALIZABLE": "SER",
            "RU": "RU",
            "RC": "RC",
            "RR": "RR",
            "SER": "SER"
        }
        short_iso = iso_map.get(isolation_level.upper().strip(), isolation_level.upper().strip())
        if "ALL" in self.disallowed_levels:
            return True
        return short_iso in [lvl.upper() for lvl in self.disallowed_levels]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "raw_pattern": self.raw_pattern,
            "disallowed_levels": self.disallowed_levels,
            "description": self.description,
            "operations": [op.to_dict() for op in self.operations],
            "cstr1": self.cstr1,
            "cstr2": self.cstr2,
            "cstr3": self.cstr3,
            "adya_dependencies": self.adya_dependencies
        }


# =====================================================================
# Table 2: Canonical Anomaly Patterns
# =====================================================================
CANONICAL_PATTERNS: List[AnomalyPattern] = [
    AnomalyPattern(
        pattern_id="C-DW",
        name="Dirty Write (G0)",
        raw_pattern="W1[x1] W2[x2] C1 C2",
        disallowed_levels=["RU", "RC", "RR", "SER", "ALL"],
        description="Transaction T2 overwrites uncommitted data item x written by T1, violating PL-1 (G0)."
    ),
    AnomalyPattern(
        pattern_id="C-DR",
        name="Dirty Read (A1 / P1)",
        raw_pattern="W1[x1] R2[x1] A1 C2",
        disallowed_levels=["RC", "RR", "SER"],
        description="Transaction T2 reads uncommitted data item x written by T1, which subsequently aborts/rolls back."
    ),
    AnomalyPattern(
        pattern_id="C-LU",
        name="Lost Update (P4)",
        raw_pattern="R1[x0] W2[x1] C2 W1[x2] C1",
        disallowed_levels=["RR", "SER"],
        description="T1 reads x0, T2 updates x to x1 and commits, then T1 overwrites x to x2, obliterating T2's update."
    ),
    AnomalyPattern(
        pattern_id="C-NRR",
        name="Non-Repeatable Read (A2 / P2)",
        raw_pattern="R1[x0] W2[x1] C2 R1[x1] C1",
        disallowed_levels=["RR", "SER"],
        description="T1 reads x0, T2 updates and commits x1, and T1 re-reads x obtaining altered value x1."
    ),
    AnomalyPattern(
        pattern_id="C-WS",
        name="Write Skew (A5B)",
        raw_pattern="R1[x0] W2[x1] W2[y1] C2 R1[y1] C1",
        disallowed_levels=["SER"],
        description="Transactions evaluate an invariant across x and y and perform disjoint updates, violating serializability."
    ),
    AnomalyPattern(
        pattern_id="C-RS",
        name="Read Skew (A5A)",
        raw_pattern="R1[x0] R2[y0] W1[y1] W2[x1] C1 C2",
        disallowed_levels=["SER"],
        description="T1 and T2 read inconsistent snapshots across correlated records x and y while updating them."
    ),
]


# =====================================================================
# Table 3: 40 Extended Anomaly Patterns by APTrans
# =====================================================================
EXTENDED_PATTERNS_SPEC = [
    ("1",  "W1[x1] R2[x1] C1 C2",                   ["RC", "RR", "SER"], "Read uncommitted before commit; commits normally"),
    ("2",  "W1[x1] C1 R2[x1] C2",                   ["RR"],              "Repeatable read observing update committed after T2 started"),
    ("3",  "W1[x1] R2[x1] C2 W1[x2] C1",             ["RC", "RR", "SER"], "Dirty read followed by second write from T1"),
    ("4",  "W1[x1] W2[y1] W2[x2] W1[y2] C1 C2",       ["ALL"],             "Interleaved write-write cycles across x and y"),
    ("5",  "W1[x1] W2[y1] W1[y2] W2[x2] C1 C2",       ["ALL"],             "Concurrent multi-variable cross writes violating PL-1"),
    ("6",  "W1[x1] W2[x2] C2 W2[y2] W1[y2] C1",       ["ALL"],             "Overlapping writes with committed middle phase"),
    ("7",  "W1[x1] W2[y1] W2[x2] C2 W1[x2] C1",       ["ALL"],             "Write overwrite on x after cross-variable updates"),
    ("8",  "W1[x1] W2[y1] W2[x2] R1[y1] C1 C2",       ["ALL"],             "Cross write with uncommitted read of y by T1"),
    ("9",  "W1[x1] W2[y1] R1[y1] W2[x2] C1 C2",       ["ALL"],             "Interleaved read of y before second write of x"),
    ("10", "W1[x1] W2[y1] W2[x2] C2 R1[y1] C1",       ["ALL"],             "Read of y after T2 commit with prior uncommitted write conflict"),
    ("11", "W1[x1] W2[y1] R1[y1] C1 W2[x2] C2",       ["RC", "RR", "SER"], "Read of uncommitted y committed before T2 second write"),
    ("12", "W1[x1] R2[y0] W2[x2] W1[y1] C1 C2",       ["ALL"],             "Stale read y followed by cross write conflict on x"),
    ("13", "W1[x1] R2[y0] W1[y1] W2[x2] C1 C2",       ["ALL"],             "Read y0 followed by conflicting writes"),
    ("14", "W1[x1] R2[y0] W2[x2] C2 W1[y1] C1",       ["ALL"],             "Write overwrite after commit with prior stale read"),
    ("15", "W1[x1] R2[y0] W1[y1] C1 W2[x2] C2",       ["RR", "SER"],       "Anti-dependency cycle across x and y"),
    ("16", "W1[x1] W2[y1] R2[x1] W1[y2] C1 C2",       ["ALL"],             "Dirty read of x inside multi-variable write loop"),
    ("17", "W1[x1] W2[y1] W1[y2] R2[x1] C1 C2",       ["ALL"],             "Deferred dirty read of x after secondary write y"),
    ("18", "W1[x1] W2[y1] R2[x1] C2 W1[y2] C1",       ["RC", "RR", "SER"], "Dirty read of x committed before T1 secondary write"),
    ("19", "W1[x1] W2[y1] W1[y2] C1 R2[x1] C2",       ["ALL"],             "Write-write race committed then read by T2"),
    ("20", "W1[x1] W2[y1] R2[x1] R1[y1] C1 C2",       ["RC", "RR", "SER"], "Dual dirty reads: T2 reads x1 and T1 reads y1"),
    ("21", "W1[x1] W2[y1] R1[y1] R2[x1] C1 C2",       ["RC", "RR", "SER"], "Symmetric dual dirty reads across transactions"),
    ("22", "W1[x1] W2[y1] R2[x1] C2 R1[y1] C1",       ["RC", "RR", "SER"], "Dirty read of x committed while y read remains uncommitted"),
    ("23", "W1[x1] W2[y1] R1[y1] C1 R2[x1] C2",       ["RC", "RR", "SER"], "Dirty read of y committed while x read remains uncommitted"),
    ("24", "W1[x1] R2[y0] R2[x1] W1[y1] C1 C2",       ["RC", "RR", "SER"], "Stale read y0 followed by dirty read x1 and write y1"),
    ("25", "W1[x1] R2[y0] W1[y1] R2[x1] C1 C2",       ["RC", "RR", "SER"], "Stale read y0, write y1, followed by dirty read x1"),
    ("26", "W1[x1] R2[y0] R2[x1] C2 W1[y1] C1",       ["RC", "RR", "SER"], "T2 commits dirty read of x before T1 writes y"),
    ("27", "W1[x1] R2[y0] W1[y1] C1 R2[x1] C2",       ["RR", "SER"],       "Snapshot inconsistency reading stale y0 and committed x1"),
    ("28", "R1[x0] W2[y1] W2[x1] W1[y2] C1 C2",       ["RC", "RR", "SER"], "Lost update variant across dual variable writes"),
    ("29", "R1[x0] W2[y1] W1[y2] W2[x1] C1 C2",       ["RC", "RR", "SER"], "Interleaved read-write dependency cycle"),
    ("30", "R1[x0] W2[x1] C2 W2[y1] W1[y2] C1",       ["RR", "SER"],       "Committed overwrite on x followed by cross write on y"),
    ("31", "R1[x0] W2[y1] W2[x1] C2 W1[x1] C1",       ["ALL"],             "Dirty write / lost update hybrid on identical value"),
    ("32", "R1[x0] W2[y1] W2[x1] R1[y1] C1 C2",       ["RC", "RR", "SER"], "Read stale x0, write y1/x1, followed by dirty read of y1"),
    ("33", "R1[x0] W2[y1] R1[y1] W2[x1] C1 C2",       ["RC", "RR", "SER"], "Interleaved dirty read of y1 before secondary write x1"),
    ("34", "R1[x0] W2[y1] W2[x1] C2 R1[y1] C1",       ["SER"],             "Serializable violation: read committed y1 after initial read x0"),
    ("35", "R1[x0] W2[y1] R1[y1] C1 W2[x1] C2",       ["RC", "RR", "SER"], "Read uncommitted y1, commit T1, followed by write x1"),
    ("36", "W1[x1] W2[y1] C2 R1[y1] C1",             ["SER"],             "Case Study 3 pattern: auto-inc / serialization cross cycle"),
    ("37", "R1[x0] R2[y0] W2[x1] W1[y1] C1 C2",       ["SER"],             "Classic Write Skew variant: concurrent independent writes"),
    ("38", "R1[x0] R2[y0] W1[y1] W2[x1] C1 C2",       ["SER"],             "Classic Read/Write Skew symmetric variant"),
    ("39", "R1[x0] R2[y0] W2[x1] C2 W1[y1] C1",       ["SER"],             "Write skew with intermediate commit of T2"),
    ("40", "R1[x0] R2[y0] W1[y1] C1 W2[x1] C2",       ["SER"],             "Write skew with intermediate commit of T1"),
]

EXTENDED_PATTERNS: List[AnomalyPattern] = [
    AnomalyPattern(
        pattern_id=f"P{item[0]}",
        name=f"Pattern {item[0]}",
        raw_pattern=item[1],
        disallowed_levels=item[2],
        description=item[3]
    )
    for item in EXTENDED_PATTERNS_SPEC
]

# Combined Master Dictionary
ALL_PATTERNS: Dict[str, AnomalyPattern] = {p.pattern_id: p for p in (CANONICAL_PATTERNS + EXTENDED_PATTERNS)}


def get_pattern(pattern_id: str) -> Optional[AnomalyPattern]:
    """Retrieve an anomaly pattern by ID (e.g. 'C-LU', 'P36', '36')."""
    if pattern_id in ALL_PATTERNS:
        return ALL_PATTERNS[pattern_id]
    alt_id = f"P{pattern_id}" if not pattern_id.startswith("P") else pattern_id[1:]
    return ALL_PATTERNS.get(alt_id)


def list_patterns(filter_level: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all patterns, optionally filtered by disallowed isolation level."""
    patterns = []
    for p in (CANONICAL_PATTERNS + EXTENDED_PATTERNS):
        if filter_level and not p.is_disallowed(filter_level):
            continue
        patterns.append(p.to_dict())
    return patterns
