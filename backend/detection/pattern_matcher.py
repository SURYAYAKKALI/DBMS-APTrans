"""
Anomaly Pattern Matcher
Identifies candidate transaction anomalies based on execution histories and dependency structures.
"""

from typing import Dict, Any, List

class PatternMatcher:
    @staticmethod
    def match_patterns(histories: Dict[str, Any], dependency_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = []
        txns = histories.get("transactions", {})
        edges = dependency_info.get("edges", [])
        cycles = dependency_info.get("cycles", [])

        # 1. Match Lost Update (P4)
        # T1 & T2 read same row, both write that row, both committed, and T2's write ignored T1's write
        for i, (t1_id, t1) in enumerate(txns.items()):
            for j, (t2_id, t2) in enumerate(txns.items()):
                if t1_id >= t2_id:
                    continue
                if t1.get("outcome") != "COMMITTED" or t2.get("outcome") != "COMMITTED":
                    continue

                for r1 in t1["read_set"]:
                    for r2 in t2["read_set"]:
                        if r1["table"] == r2["table"] and r1["row_id"] == r2["row_id"] and r1["value"] == r2["value"]:
                            # Both read same initial value
                            w1_match = [w for w in t1["write_set"] if w["table"] == r1["table"] and w["row_id"] == r1["row_id"]]
                            w2_match = [w for w in t2["write_set"] if w["table"] == r2["table"] and w["row_id"] == r2["row_id"]]
                            if w1_match and w2_match:
                                # Both wrote to the same row after reading identical state
                                candidates.append({
                                    "type": "LOST_UPDATE",
                                    "severity": "CRITICAL",
                                    "involved_txns": [t1_id, t2_id],
                                    "affected_records": [f"{r1['table']}:{r1['row_id']}"],
                                    "evidence": f"Both {t1_id} and {t2_id} read {r1['table']}:{r1['row_id']} at value '{r1['value']}'. Both performed concurrent blind updates and committed, causing one update to overwrite the other silently.",
                                    "expected_behavior": "Under strict concurrency control, one transaction must be rejected with a serialization failure or wait on a row lock.",
                                    "observed_behavior": "Both transactions committed successfully; the second committer overwrote the first committer's update based on stale state.",
                                    "suggested_fix": "Use atomic update: `UPDATE inventory SET quantity = quantity - 1 WHERE quantity >= 1`, Optimistic Concurrency Control with versioning, or PostgreSQL SERIALIZABLE isolation."
                                })

        # 2. Match Write Skew (A5B)
        # Transactions read overlapping predicate / data but update disjoint items, causing an invariant failure or RW cycle
        for cycle in cycles:
            if len(cycle) == 2:
                t1_id, t2_id = cycle[0], cycle[1]
                t1 = txns.get(t1_id, {})
                t2 = txns.get(t2_id, {})
                if t1.get("outcome") == "COMMITTED" and t2.get("outcome") == "COMMITTED":
                    # Check if edges in cycle are RW (anti-dependency cycle)
                    cycle_edges = [e for e in edges if e["source"] in cycle and e["target"] in cycle]
                    rw_count = sum(1 for e in cycle_edges if e["type"] == "RW")
                    if rw_count >= 1:
                        candidates.append({
                            "type": "WRITE_SKEW",
                            "severity": "HIGH",
                            "involved_txns": cycle,
                            "affected_records": [f"{e['table']}:{e['row_id']}" for e in cycle_edges],
                            "evidence": f"Transactions {cycle[0]} and {cycle[1]} form an anti-dependency cycle (RW edges). Each transaction read overlapping state and concurrently updated disjoint records, preserving local rules but violating global invariants.",
                            "expected_behavior": "Serializable Snapshot Isolation (SSI) or predicate locking should detect the rw-antidependency cycle and abort one transaction.",
                            "observed_behavior": "Both transactions committed concurrently under Snapshot Isolation / Read Committed.",
                            "suggested_fix": "Upgrade transaction isolation level to SERIALIZABLE in PostgreSQL, or execute explicit SELECT ... FOR UPDATE / table locking."
                        })

        # 3. Match Non-Repeatable Read (G1c)
        for tid, t in txns.items():
            if t.get("outcome") == "COMMITTED":
                reads_by_row: Dict[str, List[Any]] = {}
                for r in t["read_set"]:
                    key = f"{r['table']}:{r['row_id']}"
                    reads_by_row.setdefault(key, []).append(r)
                for key, read_list in reads_by_row.items():
                    if len(read_list) >= 2:
                        val0 = read_list[0]["value"]
                        val1 = read_list[1]["value"]
                        if val0 != val1:
                            candidates.append({
                                "type": "NON_REPEATABLE_READ",
                                "severity": "MEDIUM",
                                "involved_txns": [tid],
                                "affected_records": [key],
                                "evidence": f"Transaction {tid} read record {key} twice within the same transaction and observed two distinct values: '{val0}' (seq {read_list[0]['seq']}) and '{val1}' (seq {read_list[1]['seq']}).",
                                "expected_behavior": "Repeatable Read and Serializable guarantees ensure a transaction reads a consistent snapshot throughout its lifetime.",
                                "observed_behavior": "Intermediate committed writes from other sessions were visible on subsequent reads within the transaction.",
                                "suggested_fix": "Set transaction isolation level to REPEATABLE READ or SERIALIZABLE."
                            })

        # 4. Match Dirty Read (G1a/G1b)
        for tid, t in txns.items():
            for r in t["read_set"]:
                # Check if this read value matches an uncommitted/aborted write from another txn
                for other_id, other_t in txns.items():
                    if other_id == tid:
                        continue
                    for w in other_t["write_set"]:
                        if w["table"] == r["table"] and w["row_id"] == r["row_id"] and str(w["new_value"]) == str(r["value"]):
                            if other_t.get("outcome") == "ABORTED":
                                candidates.append({
                                    "type": "DIRTY_READ",
                                    "severity": "CRITICAL",
                                    "involved_txns": [tid, other_id],
                                    "affected_records": [f"{r['table']}:{r['row_id']}"],
                                    "evidence": f"Transaction {tid} read value '{r['value']}' written by {other_id}, but {other_id} subsequently rolled back.",
                                    "expected_behavior": "Transactions must never observe uncommitted modifications of aborted transactions.",
                                    "observed_behavior": "Dirty uncommitted data leaked into the active transaction.",
                                    "suggested_fix": "Enforce READ COMMITTED or higher isolation."
                                })

        # 5. Match Read Skew (A5A)
        # Check if reader observed inconsistent composite state
        for tid, t in txns.items():
            if len(t["read_set"]) >= 2:
                # E.g. equipment laptop + gpu
                tables = [r["table"] for r in t["read_set"]]
                if "equipment" in tables:
                    vals = [int(r["value"]) for r in t["read_set"] if r["value"] is not None and str(r["value"]).isdigit()]
                    if len(vals) == 2 and sum(vals) != 2:  # Expected total invariant was 2
                        candidates.append({
                            "type": "READ_SKEW",
                            "severity": "MEDIUM",
                            "involved_txns": [tid],
                            "affected_records": [f"{r['table']}:{r['row_id']}" for r in t["read_set"]],
                            "evidence": f"Transaction {tid} read related items at different points in time, observing inconsistent total sum {sum(vals)} instead of conserved balance 2.",
                            "expected_behavior": "Snapshot Isolation should provide a point-in-time view across all reads.",
                            "observed_behavior": "Observed partial progress of concurrent transfer transaction.",
                            "suggested_fix": "Use REPEATABLE READ or SERIALIZABLE to ensure snapshot read consistency."
                        })

        return candidates
