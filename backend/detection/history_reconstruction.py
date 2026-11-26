"""
Transaction History Reconstruction Engine
Orders execution events chronologically and builds structured per-transaction lifecycles.
"""

from typing import List, Dict, Any

class HistoryReconstructor:
    @staticmethod
    def reconstruct(events: List[Dict[str, Any]], transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Takes raw operation events and transaction records;
        Produces structured chronological histories per transaction and global sequence.
        """
        # Sort events by global sequence
        sorted_events = sorted(events, key=lambda e: e.get("sequence", 0))

        txn_map = {t["txn_id"]: dict(t) for t in transactions}
        for t in txn_map.values():
            t["operations"] = []
            t["read_set"] = []
            t["write_set"] = []

        for evt in sorted_events:
            tid = evt.get("txn_id")
            if tid not in txn_map:
                txn_map[tid] = {
                    "txn_id": tid,
                    "session_id": evt.get("session_id", "UNKNOWN"),
                    "isolation_level": "UNKNOWN",
                    "outcome": evt.get("status", "ACTIVE"),
                    "operations": [],
                    "read_set": [],
                    "write_set": []
                }

            txn_map[tid]["operations"].append(evt)
            op = evt.get("operation_type")
            table = evt.get("table_name")
            row = evt.get("row_id")

            if op == "READ":
                txn_map[tid]["read_set"].append({
                    "table": table,
                    "row_id": row,
                    "value": evt.get("old_value"),
                    "version": evt.get("version"),
                    "seq": evt.get("sequence")
                })
            elif op in ["WRITE", "UPDATE", "INSERT"]:
                txn_map[tid]["write_set"].append({
                    "table": table,
                    "row_id": row,
                    "old_value": evt.get("old_value"),
                    "new_value": evt.get("new_value"),
                    "version": evt.get("version"),
                    "seq": evt.get("sequence")
                })

        return {
            "transactions": txn_map,
            "global_history": sorted_events
        }
