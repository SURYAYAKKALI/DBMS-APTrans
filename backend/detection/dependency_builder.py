"""
Dependency Graph Construction Engine
Constructs directed dependency graphs with WR, RW, and WW edges using NetworkX.
"""

import uuid
import networkx as nx
from typing import Dict, Any, List

class DependencyBuilder:
    @staticmethod
    def build_dependencies(histories: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        """
        Extracts dependencies across transactions:
        - WR: T1 writes item X, T2 reads X written by T1
        - RW (Anti-dependency): T1 reads item X, T2 writes a new version of X
        - WW: T1 writes item X, T2 subsequently overwrites X
        """
        txns = histories.get("transactions", {})
        G = nx.DiGraph()

        for tid, tinfo in txns.items():
            G.add_node(
                tid,
                label=tid,
                session=tinfo.get("session_id"),
                isolation=tinfo.get("isolation_level"),
                outcome=tinfo.get("outcome")
            )

        edges: List[Dict[str, Any]] = []
        txn_ids = list(txns.keys())

        for i in range(len(txn_ids)):
            for j in range(len(txn_ids)):
                if i == j:
                    continue
                t1_id = txn_ids[i]
                t2_id = txn_ids[j]
                t1 = txns[t1_id]
                t2 = txns[t2_id]

                # Check WW (Write-Write dependency)
                for w1 in t1["write_set"]:
                    for w2 in t2["write_set"]:
                        if w1["table"] == w2["table"] and w1["row_id"] == w2["row_id"]:
                            if w1["seq"] < w2["seq"]:
                                edge = {
                                    "edge_id": f"DEP-{uuid.uuid4().hex[:8].upper()}",
                                    "source": t1_id,
                                    "target": t2_id,
                                    "type": "WW",
                                    "table": w1["table"],
                                    "row_id": w1["row_id"],
                                    "details": f"WW: {t1_id} write (seq {w1['seq']}) precedes {t2_id} write (seq {w2['seq']})"
                                }
                                edges.append(edge)
                                G.add_edge(t1_id, t2_id, type="WW", table=w1["table"], row_id=w1["row_id"])

                # Check WR (Write-Read dependency)
                for w1 in t1["write_set"]:
                    for r2 in t2["read_set"]:
                        if w1["table"] == r2["table"] and w1["row_id"] == r2["row_id"]:
                            if w1["seq"] < r2["seq"]:
                                edge = {
                                    "edge_id": f"DEP-{uuid.uuid4().hex[:8].upper()}",
                                    "source": t1_id,
                                    "target": t2_id,
                                    "type": "WR",
                                    "table": w1["table"],
                                    "row_id": w1["row_id"],
                                    "details": f"WR: {t2_id} reads (seq {r2['seq']}) after {t1_id} write (seq {w1['seq']})"
                                }
                                edges.append(edge)
                                G.add_edge(t1_id, t2_id, type="WR", table=w1["table"], row_id=w1["row_id"])

                # Check RW (Read-Write anti-dependency)
                for r1 in t1["read_set"]:
                    for w2 in t2["write_set"]:
                        if r1["table"] == w2["table"] and r1["row_id"] == w2["row_id"]:
                            if r1["seq"] < w2["seq"]:
                                edge = {
                                    "edge_id": f"DEP-{uuid.uuid4().hex[:8].upper()}",
                                    "source": t1_id,
                                    "target": t2_id,
                                    "type": "RW",
                                    "table": r1["table"],
                                    "row_id": r1["row_id"],
                                    "details": f"RW: {t1_id} read (seq {r1['seq']}) precedes {t2_id} overwrite (seq {w2['seq']})"
                                }
                                edges.append(edge)
                                G.add_edge(t1_id, t2_id, type="RW", table=r1["table"], row_id=r1["row_id"])

        # Detect cycles
        cycles = []
        try:
            cycles = list(nx.simple_cycles(G))
        except Exception:
            pass

        cycle_nodes = set()
        for c in cycles:
            cycle_nodes.update(c)

        for edge in edges:
            edge["is_cycle_member"] = (edge["source"] in cycle_nodes and edge["target"] in cycle_nodes)

        # Build React Flow graph format
        react_flow_nodes = []
        for idx, (node, data) in enumerate(G.nodes(data=True)):
            react_flow_nodes.append({
                "id": node,
                "type": "transactionNode",
                "position": {"x": 100 + (idx * 260), "y": 150 + ((idx % 2) * 120)},
                "data": {
                    "label": node,
                    "session": data.get("session"),
                    "isolation": data.get("isolation"),
                    "outcome": data.get("outcome"),
                    "in_cycle": node in cycle_nodes
                }
            })

        react_flow_edges = []
        for edge in edges:
            color = "#ef4444" if edge["type"] == "RW" else ("#3b82f6" if edge["type"] == "WR" else "#f59e0b")
            react_flow_edges.append({
                "id": edge["edge_id"],
                "source": edge["source"],
                "target": edge["target"],
                "label": edge["type"],
                "type": "smoothstep",
                "animated": edge.get("is_cycle_member", False),
                "style": {"stroke": color, "strokeWidth": 2},
                "data": edge
            })

        return {
            "graph": G,
            "edges": edges,
            "cycles": cycles,
            "cycle_nodes": list(cycle_nodes),
            "react_flow": {
                "nodes": react_flow_nodes,
                "edges": react_flow_edges
            }
        }
