"""
DBGuard Lock Manager & Deadlock Detector
Implements InnoDB row-level locking (Exclusive/Shared),
Wait-For Graph (WFG) maintenance, and cycle detection (MySQL Error 1213).
"""

import time
import threading
from collections import defaultdict

class DeadlockException(Exception):
    """Corresponds to MySQL Error 1213: Deadlock found when trying to get lock."""
    def __init__(self, message="Deadlock found when trying to get lock; try restarting transaction", cycle=None):
        super().__init__(message)
        self.error_code = 1213
        self.cycle = cycle or []

class LockTimeoutException(Exception):
    """Corresponds to MySQL Error 1205: Lock wait timeout exceeded."""
    def __init__(self, message="Lock wait timeout exceeded; try restarting transaction"):
        super().__init__(message)
        self.error_code = 1205

class LockManager:
    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(LockManager, cls).__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self.mutex = threading.RLock()
        # resource_id -> {"owner": tx_id, "mode": "EXCLUSIVE" | "SHARED", "waiting": [tx_id, ...]}
        self.locks = {}
        # Wait-For Graph: waiting_tx -> set of holder_tx
        self.wait_for_graph = defaultdict(set)
        # Conditions for threads waiting for a resource: resource_id -> threading.Condition
        self.conditions = {}
        # Transaction holding resources: tx_id -> set of resource_ids
        self.tx_held_resources = defaultdict(set)
        # Stats
        self.total_locks_acquired = 0
        self.total_deadlocks_detected = 0
        self.total_lock_wait_ms = 0.0

    def reset(self):
        """Reset lock manager state."""
        with self.mutex:
            self.locks.clear()
            self.wait_for_graph.clear()
            self.conditions.clear()
            self.tx_held_resources.clear()

    def acquire_lock(self, resource_id, tx_id, mode="EXCLUSIVE", timeout_sec=5.0):
        """
        Acquire a lock on a resource for a transaction.
        Detects deadlocks before waiting.
        """
        start_time = time.time()

        with self.mutex:
            # If the transaction already holds this resource, it's a re-entrant acquisition
            if resource_id in self.locks and self.locks[resource_id]["owner"] == tx_id:
                return {"status": "ALREADY_HELD", "resource": resource_id, "wait_ms": 0}

            # Check if resource is free
            if resource_id not in self.locks:
                self.locks[resource_id] = {
                    "owner": tx_id,
                    "mode": mode,
                    "waiting": []
                }
                self.tx_held_resources[tx_id].add(resource_id)
                self.total_locks_acquired += 1
                return {"status": "ACQUIRED_IMMEDIATELY", "resource": resource_id, "wait_ms": 0}

            # Resource is locked by another transaction
            current_owner = self.locks[resource_id]["owner"]
            if current_owner == tx_id:
                return {"status": "HELD", "resource": resource_id, "wait_ms": 0}

            # Add edge to Wait-For Graph: tx_id is waiting for current_owner
            self.wait_for_graph[tx_id].add(current_owner)

            # Check for cycle in Wait-For Graph (Deadlock detection)
            cycle = self._detect_deadlock_cycle(tx_id)
            if cycle:
                # Remove edge
                self.wait_for_graph[tx_id].remove(current_owner)
                self.total_deadlocks_detected += 1
                raise DeadlockException(
                    message=f"Deadlock found when trying to get lock on '{resource_id}' by transaction '{tx_id}'. Cycle detected: {' -> '.join(cycle)}",
                    cycle=cycle
                )

            # Register as waiting
            self.locks[resource_id]["waiting"].append(tx_id)
            if resource_id not in self.conditions:
                self.conditions[resource_id] = threading.Condition(self.mutex)
            cond = self.conditions[resource_id]

        # Wait on condition
        with cond:
            deadline = start_time + timeout_sec
            while True:
                with self.mutex:
                    # Check if we can now claim the lock
                    if resource_id not in self.locks:
                        # Resource was freed!
                        self.locks[resource_id] = {
                            "owner": tx_id,
                            "mode": mode,
                            "waiting": []
                        }
                        self.tx_held_resources[tx_id].add(resource_id)
                        # Remove from wait graph
                        if current_owner in self.wait_for_graph[tx_id]:
                            self.wait_for_graph[tx_id].remove(current_owner)
                        wait_ms = (time.time() - start_time) * 1000.0
                        self.total_lock_wait_ms += wait_ms
                        self.total_locks_acquired += 1
                        return {"status": "ACQUIRED_AFTER_WAIT", "resource": resource_id, "wait_ms": round(wait_ms, 2)}

                remaining = deadline - time.time()
                if remaining <= 0:
                    with self.mutex:
                        if current_owner in self.wait_for_graph[tx_id]:
                            self.wait_for_graph[tx_id].remove(current_owner)
                        if resource_id in self.locks and tx_id in self.locks[resource_id]["waiting"]:
                            self.locks[resource_id]["waiting"].remove(tx_id)
                    raise LockTimeoutException(f"Lock wait timeout exceeded ({timeout_sec}s) on '{resource_id}'.")

                cond.wait(timeout=remaining)

    def release_locks_for_tx(self, tx_id):
        """Release all locks held by a transaction on commit or rollback."""
        with self.mutex:
            held = list(self.tx_held_resources.get(tx_id, set()))
            for res_id in held:
                if res_id in self.locks and self.locks[res_id]["owner"] == tx_id:
                    del self.locks[res_id]
                    if res_id in self.conditions:
                        with self.conditions[res_id]:
                            self.conditions[res_id].notify_all()

            if tx_id in self.tx_held_resources:
                del self.tx_held_resources[tx_id]

            # Remove from wait graph
            if tx_id in self.wait_for_graph:
                del self.wait_for_graph[tx_id]
            for waiting_tx, holders in list(self.wait_for_graph.items()):
                holders.discard(tx_id)

    def _detect_deadlock_cycle(self, start_tx):
        """
        DFS cycle detection in the Wait-For Graph.
        Returns the path forming the cycle if detected, or None.
        """
        visited = set()
        stack = []

        def dfs(node):
            visited.add(node)
            stack.append(node)
            for neighbor in self.wait_for_graph.get(node, []):
                if neighbor in stack:
                    # Cycle found!
                    cycle_start_idx = stack.index(neighbor)
                    return stack[cycle_start_idx:] + [neighbor]
                if neighbor not in visited:
                    res = dfs(neighbor)
                    if res:
                        return res
            stack.pop()
            return None

        return dfs(start_tx)

    def get_lock_stats(self):
        """Telemetry on lock waits, held locks, and deadlocks."""
        with self.mutex:
            return {
                "active_locks_count": len(self.locks),
                "active_locks": {
                    k: {"owner": v["owner"], "mode": v["mode"], "waiting": list(v["waiting"])}
                    for k, v in self.locks.items()
                },
                "wait_for_graph": {k: list(v) for k, v in self.wait_for_graph.items() if v},
                "total_acquired": self.total_locks_acquired,
                "total_deadlocks": self.total_deadlocks_detected,
                "avg_wait_ms": round(self.total_lock_wait_ms / max(1, self.total_locks_acquired), 2)
            }
