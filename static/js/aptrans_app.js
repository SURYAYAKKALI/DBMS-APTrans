/**
 * APTrans Interactive Web Application Logic
 * Reconstructing "Anomaly Pattern-guided Transaction Bug Testing in Relational Databases" (SIGMOD 2026)
 * Includes Live Concurrency Studio: Visualizing Problems Live and Solving Them
 */

document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initLiveSimulator(); // Instant! 0ms! Loads in-memory immediately
    initScheduler();
    initDetector();
});

// Master Application State
const APState = {
    currentTab: "livesim", // Default landing on the interactive problem vs solution studio!
    patterns: [],
    selectedPatternId: "C-LU",
    currentCase: null,
    currentTrace: null,
    currentReport: null
};

// Track which tabs have been fetched to enable instant, lazy-loaded navigation
const LoadedTabs = {
    livesim: true,
    patterns: false,
    generator: false,
    scheduler: true,
    detector: true,
    casestudies: false,
    benchmarks: false,
    critique: false,
    evaluation: false
};

// -------------------------------------------------------------
// Navigation Manager
// -------------------------------------------------------------
function initNavigation() {
    const navButtons = document.querySelectorAll("[data-nav-tab]");
    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-nav-tab");
            switchTab(targetTab);
        });
    });
}

function switchTab(tabId) {
    APState.currentTab = tabId;
    
    // Update button styles
    document.querySelectorAll("[data-nav-tab]").forEach(btn => {
        const isCurrent = btn.getAttribute("data-nav-tab") === tabId;
        if (isCurrent) {
            btn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 text-xs font-bold shadow-sm transition";
        } else {
            btn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-800/60 text-xs font-medium transition";
        }
    });

    // Update section visibility
    document.querySelectorAll("[data-tab-content]").forEach(sec => {
        if (sec.getAttribute("data-tab-content") === tabId) {
            sec.classList.remove("hidden");
        } else {
            sec.classList.add("hidden");
        }
    });

    // Lazy load tab data on-demand (avoids blocking initial render!)
    if (tabId === "patterns" && !LoadedTabs.patterns) {
        LoadedTabs.patterns = true;
        initPatternCatalog();
    } else if (tabId === "generator" && !LoadedTabs.generator) {
        LoadedTabs.generator = true;
        initGenerator();
    } else if (tabId === "casestudies" && !LoadedTabs.casestudies) {
        LoadedTabs.casestudies = true;
        initCaseStudies();
    } else if (tabId === "benchmarks" && !LoadedTabs.benchmarks) {
        LoadedTabs.benchmarks = true;
        initBenchmarks();
    } else if (tabId === "critique" && !LoadedTabs.critique) {
        LoadedTabs.critique = true;
        initCritique();
    } else if (tabId === "evaluation" && !LoadedTabs.evaluation) {
        LoadedTabs.evaluation = true;
        initEvaluation();
    }

    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// =============================================================
// TAB 0: LIVE CONCURRENCY STUDIO (BREAK IT & FIX IT)
// =============================================================
const LIVE_SCENARIOS = {
    lost_update: {
        title: "Lost Update Anomaly (P4)",
        category: "Race Condition on Ledger Balance",
        description: "Two concurrent transactions read the same initial balance ($1000) and perform disjoint updates. Without locks, one update overwrites the other, causing silent data loss.",
        initialState: { resource: "Account ACC-0001 (Alice Johnson)", balance: 1000.00, version: 1, lockOwner: "None" },
        modes: {
            unsafe: {
                label: "Unsafe (Trigger Bug)",
                badgeClass: "bg-rose-950 text-rose-300 border-rose-800",
                buttonClass: "bg-rose-600 hover:bg-rose-500",
                steps: [
                    { step: 1, txn: 1, action: "READ", sql: "SELECT balance FROM accounts WHERE id = 1;", detail: "T1 reads balance = $1000.00 into memory", t1Local: "$1000.00", t2Local: "-", dbBalance: 1000.00, version: 1, lock: "None", edge: null },
                    { step: 2, txn: 2, action: "READ (UNSAFE)", sql: "SELECT balance FROM accounts WHERE id = 1;", detail: "T2 concurrently reads balance = $1000.00 without lock!", t1Local: "$1000.00", t2Local: "$1000.00", dbBalance: 1000.00, version: 1, lock: "None", edge: null },
                    { step: 3, txn: 1, action: "CALCULATE", sql: "T1 calculates $1000.00 - $100.00 = $900.00", detail: "T1 prepares to write $900.00", t1Local: "$900.00", t2Local: "$1000.00", dbBalance: 1000.00, version: 1, lock: "None", edge: null },
                    { step: 4, txn: 1, action: "WRITE & COMMIT", sql: "UPDATE accounts SET balance = 900 WHERE id = 1; COMMIT;", detail: "T1 commits $900.00 to database", t1Local: "$900.00 (Committed)", t2Local: "$1000.00", dbBalance: 900.00, version: 1, lock: "None", edge: { from: 1, to: 2, type: "rw", label: "T1 writes after T2 read" } },
                    { step: 5, txn: 2, action: "CALCULATE (STALE)", sql: "T2 calculates $1000.00 - $200.00 = $800.00", detail: "T2 uses STALE read of $1000 instead of current $900!", t1Local: "$900.00", t2Local: "$800.00", dbBalance: 900.00, version: 1, lock: "None", edge: null },
                    { step: 6, txn: 2, action: "WRITE & COMMIT (OVERWRITE)", sql: "UPDATE accounts SET balance = 800 WHERE id = 1; COMMIT;", detail: "T2 writes $800.00, completely obliterating T1's $100 deduction!", t1Local: "$900.00", t2Local: "$800.00 (Committed)", dbBalance: 800.00, version: 1, lock: "None", edge: { from: 2, to: 1, type: "ww", label: "T2 overwrote T1 write" } }
                ],
                finalVerdict: {
                    isBug: true,
                    expected: "$700.00 ($1000 - $100 - $200)",
                    actual: "$800.00",
                    loss: "$100.00 SILENT DATA LOSS",
                    msg: "CONCURRENCY BUG CONFIRMED! T1's $100 deduction was completely wiped out by T2's stale write."
                }
            },
            pessimistic: {
                label: "Solve: Pessimistic 2PL (SELECT FOR UPDATE)",
                badgeClass: "bg-emerald-950 text-emerald-300 border-emerald-800",
                buttonClass: "bg-emerald-600 hover:bg-emerald-500",
                steps: [
                    { step: 1, txn: 1, action: "LOCK & READ", sql: "SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;", detail: "T1 acquires Exclusive Row Lock. Reads balance = $1000.00", t1Local: "$1000.00", t2Local: "-", dbBalance: 1000.00, version: 1, lock: "Held by T1 (Exclusive)", edge: null },
                    { step: 2, txn: 2, action: "LOCK_WAIT (BLOCKED)", sql: "SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;", detail: "T2 tries to lock Account 1 -> BLOCKED in waitTxn queue!", t1Local: "$1000.00", t2Local: "BLOCKED (Waiting...)", dbBalance: 1000.00, version: 1, lock: "Held by T1 (Exclusive)", edge: { from: 2, to: 1, type: "wait", label: "T2 waits for T1 lock" } },
                    { step: 3, txn: 1, action: "WRITE & RELEASE", sql: "UPDATE accounts SET balance = 900 WHERE id = 1; COMMIT;", detail: "T1 commits $900.00 and RELEASES row lock!", t1Local: "$900.00 (Committed)", t2Local: "BLOCKED (Waking up...)", dbBalance: 900.00, version: 1, lock: "Released", edge: null },
                    { step: 4, txn: 2, action: "LOCK ACQUIRED & READ FRESH", sql: "SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;", detail: "T2 unblocks, acquires lock, and reads FRESH committed balance = $900.00!", t1Local: "$900.00", t2Local: "$900.00 (Fresh)", dbBalance: 900.00, version: 1, lock: "Held by T2 (Exclusive)", edge: { from: 1, to: 2, type: "wr", label: "T2 reads T1 write" } },
                    { step: 5, txn: 2, action: "CALCULATE", sql: "T2 calculates $900.00 - $200.00 = $700.00", detail: "T2 computes correct serialized balance", t1Local: "$900.00", t2Local: "$700.00", dbBalance: 900.00, version: 1, lock: "Held by T2", edge: null },
                    { step: 6, txn: 2, action: "WRITE & COMMIT", sql: "UPDATE accounts SET balance = 700 WHERE id = 1; COMMIT;", detail: "T2 commits $700.00 and releases lock. Execution serialized cleanly!", t1Local: "$900.00", t2Local: "$700.00 (Committed)", dbBalance: 700.00, version: 1, lock: "None", edge: null }
                ],
                finalVerdict: {
                    isBug: false,
                    expected: "$700.00",
                    actual: "$700.00",
                    loss: "$0.00 (Zero Loss)",
                    msg: "PROBLEM SOLVED! Pessimistic locking forced T2 into LOCK_WAIT until T1 committed. 100% Invariant Preserved!"
                }
            },
            optimistic: {
                label: "Solve: Optimistic OCC (Version Check)",
                badgeClass: "bg-purple-950 text-purple-300 border-purple-800",
                buttonClass: "bg-purple-600 hover:bg-purple-500",
                steps: [
                    { step: 1, txn: 1, action: "READ VERSION", sql: "SELECT balance, version FROM accounts WHERE id = 1;", detail: "T1 reads balance=$1000.00, version=1", t1Local: "$1000 (v1)", t2Local: "-", dbBalance: 1000.00, version: 1, lock: "None", edge: null },
                    { step: 2, txn: 2, action: "READ VERSION", sql: "SELECT balance, version FROM accounts WHERE id = 1;", detail: "T2 reads balance=$1000.00, version=1", t1Local: "$1000 (v1)", t2Local: "$1000 (v1)", dbBalance: 1000.00, version: 1, lock: "None", edge: null },
                    { step: 3, txn: 1, action: "UPDATE WITH VERSION=1", sql: "UPDATE accounts SET balance = 900, version = 2 WHERE id = 1 AND version = 1;", detail: "T1 writes successfully (1 row affected, version becomes 2)", t1Local: "$900 (v2)", t2Local: "$1000 (v1)", dbBalance: 900.00, version: 2, lock: "None", edge: null },
                    { step: 4, txn: 1, action: "COMMIT", sql: "COMMIT;", detail: "T1 committed safely.", t1Local: "$900 (Committed)", t2Local: "$1000 (v1)", dbBalance: 900.00, version: 2, lock: "None", edge: null },
                    { step: 5, txn: 2, action: "CONFLICT DETECTED!", sql: "UPDATE accounts SET balance = 800, version = 2 WHERE id = 1 AND version = 1;", detail: "0 rows affected! Stale version=1 detected. Database rejects overwrite!", t1Local: "$900", t2Local: "CONFLICT ABORT", dbBalance: 900.00, version: 2, lock: "None", edge: null },
                    { step: 6, txn: 2, action: "RETRY WITH VERSION 2", sql: "UPDATE accounts SET balance = 700, version = 3 WHERE id = 1 AND version = 2; COMMIT;", detail: "T2 re-reads balance=$900 (v2), calculates $700, and commits version 3!", t1Local: "$900", t2Local: "$700 (v3 Committed)", dbBalance: 700.00, version: 3, lock: "None", edge: null }
                ],
                finalVerdict: {
                    isBug: false,
                    expected: "$700.00",
                    actual: "$700.00",
                    loss: "$0.00 (Zero Loss)",
                    msg: "PROBLEM SOLVED! Optimistic concurrency control caught version mismatch, rejected stale write, and retried cleanly!"
                }
            }
        }
    },
    double_booking: {
        title: "Double-Booking Anomaly (A5B)",
        category: "Phantom Seat Allocation Conflict",
        description: "Two users simultaneously try to reserve the last remaining seat (Seat 12A). Without concurrency controls, both receive booking confirmations for the exact same seat.",
        initialState: { resource: "Flight FL-102 Seat 12A", balance: "AVAILABLE", version: 1, lockOwner: "None" },
        modes: {
            unsafe: {
                label: "Unsafe (Trigger Double-Booking)",
                badgeClass: "bg-rose-950 text-rose-300 border-rose-800",
                buttonClass: "bg-rose-600 hover:bg-rose-500",
                steps: [
                    { step: 1, txn: 1, action: "CHECK SEAT", sql: "SELECT status FROM seats WHERE seat_no = '12A';", detail: "User 1 (Alice) checks Seat 12A -> AVAILABLE", t1Local: "12A is AVAILABLE", t2Local: "-", dbBalance: "AVAILABLE", version: 1, lock: "None", edge: null },
                    { step: 2, txn: 2, action: "CHECK SEAT", sql: "SELECT status FROM seats WHERE seat_no = '12A';", detail: "User 2 (Bob) concurrently checks Seat 12A -> AVAILABLE", t1Local: "12A is AVAILABLE", t2Local: "12A is AVAILABLE", dbBalance: "AVAILABLE", version: 1, lock: "None", edge: null },
                    { step: 3, txn: 1, action: "BOOK SEAT", sql: "INSERT INTO reservations (seat_no, user) VALUES ('12A', 'Alice'); COMMIT;", detail: "User 1 confirms booking for 12A. Status -> CONFIRMED", t1Local: "CONFIRMED (Alice)", t2Local: "12A is AVAILABLE", dbBalance: "RESERVED (Alice)", version: 1, lock: "None", edge: null },
                    { step: 4, txn: 2, action: "BOOK SEAT (OVERLAP)", sql: "INSERT INTO reservations (seat_no, user) VALUES ('12A', 'Bob'); COMMIT;", detail: "User 2 ALSO confirms booking for 12A! Both transactions commit!", t1Local: "CONFIRMED (Alice)", t2Local: "CONFIRMED (Bob)", dbBalance: "DOUBLE BOOKED (Alice & Bob)", version: 1, lock: "None", edge: { from: 1, to: 2, type: "ww", label: "Both booked Seat 12A" } }
                ],
                finalVerdict: {
                    isBug: true,
                    expected: "1 Passenger Confirmed",
                    actual: "2 Passengers Confirmed (Alice & Bob)",
                    loss: "AIRLINE CRISIS: DOUBLE BOOKING",
                    msg: "CONCURRENCY BUG CONFIRMED! Two customers were issued boarding passes for the exact same physical seat."
                }
            },
            safe: {
                label: "Solve: Lock + UNIQUE(flight, seat)",
                badgeClass: "bg-emerald-950 text-emerald-300 border-emerald-800",
                buttonClass: "bg-emerald-600 hover:bg-emerald-500",
                steps: [
                    { step: 1, txn: 1, action: "LOCK & CHECK", sql: "SELECT status FROM seats WHERE seat_no = '12A' FOR UPDATE;", detail: "User 1 locks Seat 12A. Status is AVAILABLE.", t1Local: "Locked Seat 12A", t2Local: "-", dbBalance: "AVAILABLE (Locked by T1)", version: 1, lock: "Held by T1", edge: null },
                    { step: 2, txn: 2, action: "LOCK WAIT", sql: "SELECT status FROM seats WHERE seat_no = '12A' FOR UPDATE;", detail: "User 2 attempts to lock Seat 12A -> Blocked in wait queue!", t1Local: "Locked Seat 12A", t2Local: "BLOCKED (Waiting...)", dbBalance: "AVAILABLE (Locked by T1)", version: 1, lock: "Held by T1", edge: { from: 2, to: 1, type: "wait", label: "T2 waiting on Seat 12A" } },
                    { step: 3, txn: 1, action: "RESERVE & COMMIT", sql: "INSERT INTO reservations VALUES ('12A', 'Alice'); COMMIT;", detail: "User 1 reserves Seat 12A and commits. Lock released.", t1Local: "BOOKED (Alice)", t2Local: "BLOCKED (Waking up...)", dbBalance: "RESERVED (Alice)", version: 2, lock: "Released", edge: null },
                    { step: 4, txn: 2, action: "SEAT OCCUPIED -> ABORT", sql: "SELECT status FROM seats WHERE seat_no = '12A';", detail: "User 2 unblocks, observes status is RESERVED! Safely aborts and offers Seat 12B.", t1Local: "BOOKED (Alice)", t2Local: "REJECTED (Offer 12B)", dbBalance: "RESERVED (Alice)", version: 2, lock: "None", edge: null }
                ],
                finalVerdict: {
                    isBug: false,
                    expected: "1 Passenger (Alice)",
                    actual: "1 Passenger (Alice)",
                    loss: "0 Double Bookings",
                    msg: "PROBLEM SOLVED! Row locking and integrity constraints prevented duplicate seat allocation."
                }
            }
        }
    },
    dirty_read: {
        title: "Dirty Read Hazard (A1 / MySQL Bug #117835)",
        category: "Uncommitted State Leakage",
        description: "Transaction 1 modifies balance to $0.00. Transaction 2 reads the uncommitted $0.00 and acts upon it. Transaction 1 then rolls back, leaving T2 with invalid state.",
        initialState: { resource: "Account ACC-0001", balance: 1000.00, version: 1, lockOwner: "None" },
        modes: {
            unsafe: {
                label: "Unsafe (Trigger Dirty Read)",
                badgeClass: "bg-rose-950 text-rose-300 border-rose-800",
                buttonClass: "bg-rose-600 hover:bg-rose-500",
                steps: [
                    { step: 1, txn: 1, action: "UNCOMMITTED WRITE", sql: "UPDATE accounts SET balance = 0 WHERE id = 1;", detail: "T1 updates balance to $0.00 (Uncommitted in private undo space)", t1Local: "$0.00 (Uncommitted)", t2Local: "-", dbBalance: 0.00, version: 2, lock: "Held by T1", edge: null },
                    { step: 2, txn: 2, action: "DIRTY READ", sql: "SELECT balance FROM accounts WHERE id = 1;", detail: "T2 reads uncommitted $0.00 under weak isolation!", t1Local: "$0.00", t2Local: "$0.00 (DIRTY READ)", dbBalance: 0.00, version: 2, lock: "Held by T1", edge: { from: 1, to: 2, type: "wr", label: "T2 read uncommitted T1 write" } },
                    { step: 3, txn: 1, action: "ROLLBACK", sql: "ROLLBACK;", detail: "T1 encounters error and ROLLS BACK! Balance restored to $1000.00!", t1Local: "ABORTED", t2Local: "$0.00 (Phantom!)", dbBalance: 1000.00, version: 1, lock: "None", edge: null },
                    { step: 4, txn: 2, action: "ACT ON DIRTY VALUE", sql: "INSERT INTO loan_decisions VALUES (1, 'REJECTED_ZERO_BALANCE'); COMMIT;", detail: "T2 committed a critical decision based on data that NEVER EXISTED!", t1Local: "ABORTED", t2Local: "COMMITTED WITH DIRTY DATA", dbBalance: 1000.00, version: 1, lock: "None", edge: null }
                ],
                finalVerdict: {
                    isBug: true,
                    expected: "Read Confirmed $1000.00",
                    actual: "Read Phantom $0.00",
                    loss: "DATA INTEGRITY CORRUPTED",
                    msg: "CONCURRENCY BUG CONFIRMED! T2 read uncommitted write from T1 which subsequently aborted."
                }
            },
            safe: {
                label: "Solve: Read Committed MVCC Snapshot",
                badgeClass: "bg-emerald-950 text-emerald-300 border-emerald-800",
                buttonClass: "bg-emerald-600 hover:bg-emerald-500",
                steps: [
                    { step: 1, txn: 1, action: "UNCOMMITTED WRITE", sql: "UPDATE accounts SET balance = 0 WHERE id = 1;", detail: "T1 updates balance to $0.00 (Uncommitted)", t1Local: "$0.00 (Uncommitted)", t2Local: "-", dbBalance: 0.00, version: 2, lock: "Held by T1", edge: null },
                    { step: 2, txn: 2, action: "MVCC SNAPSHOT READ", sql: "SELECT balance FROM accounts WHERE id = 1;", detail: "T2 uses Read Committed MVCC snapshot! Ignores uncommitted 0, reads committed $1000.00!", t1Local: "$0.00", t2Local: "$1000.00 (Clean Snapshot)", dbBalance: 0.00, version: 2, lock: "Held by T1", edge: null },
                    { step: 3, txn: 1, action: "ROLLBACK", sql: "ROLLBACK;", detail: "T1 rolls back. Uncommitted write erased.", t1Local: "ABORTED", t2Local: "$1000.00", dbBalance: 1000.00, version: 1, lock: "None", edge: null },
                    { step: 4, txn: 2, action: "COMMIT CLEAN", sql: "INSERT INTO loan_decisions VALUES (1, 'APPROVED_VALID_BALANCE'); COMMIT;", detail: "T2 commits with 100% verified state.", t1Local: "ABORTED", t2Local: "COMMITTED CLEAN", dbBalance: 1000.00, version: 1, lock: "None", edge: null }
                ],
                finalVerdict: {
                    isBug: false,
                    expected: "Read Confirmed $1000.00",
                    actual: "Read Confirmed $1000.00",
                    loss: "0 Dirty Reads",
                    msg: "PROBLEM SOLVED! MVCC snapshot read ensured T2 only saw committed data, shielding against rollback."
                }
            }
        }
    },
    deadlock: {
        title: "Deadlock Knot & Auto-Retry",
        category: "Cyclic Wait-For Graph Lock Hazard",
        description: "Transaction 1 holds Resource A and requests Resource B. Transaction 2 holds Resource B and requests Resource A. A cyclic dependency freezes execution.",
        initialState: { resource: "Account 1 & Account 2", balance: "$1000 / $1000", version: 1, lockOwner: "None" },
        modes: {
            unsafe: {
                label: "Unsafe (Trigger Deadlock Crash)",
                badgeClass: "bg-rose-950 text-rose-300 border-rose-800",
                buttonClass: "bg-rose-600 hover:bg-rose-500",
                steps: [
                    { step: 1, txn: 1, action: "LOCK A", sql: "SELECT * FROM accounts WHERE id = 1 FOR UPDATE;", detail: "T1 acquires exclusive lock on Account 1", t1Local: "Holds Lock(Acc1)", t2Local: "-", dbBalance: "Acc1: Locked by T1", version: 1, lock: "Acc1: T1", edge: null },
                    { step: 2, txn: 2, action: "LOCK B", sql: "SELECT * FROM accounts WHERE id = 2 FOR UPDATE;", detail: "T2 acquires exclusive lock on Account 2", t1Local: "Holds Lock(Acc1)", t2Local: "Holds Lock(Acc2)", dbBalance: "Acc1: T1, Acc2: T2", version: 1, lock: "Acc1: T1, Acc2: T2", edge: null },
                    { step: 3, txn: 1, action: "REQUEST B -> WAITING", sql: "SELECT * FROM accounts WHERE id = 2 FOR UPDATE;", detail: "T1 requests Account 2 (held by T2) -> T1 is BLOCKED waiting on T2", t1Local: "WAITING on Acc2", t2Local: "Holds Lock(Acc2)", dbBalance: "Acc1: T1, Acc2: T2", version: 1, lock: "T1 waits for T2", edge: { from: 1, to: 2, type: "wait", label: "T1 waits on T2" } },
                    { step: 4, txn: 2, action: "REQUEST A -> DEADLOCK!", sql: "SELECT * FROM accounts WHERE id = 1 FOR UPDATE;", detail: "T2 requests Account 1 (held by T1) -> CYCLE DETECTED! (T1 -> T2 -> T1)", t1Local: "WAITING on Acc2", t2Local: "WAITING on Acc1", dbBalance: "DEADLOCK CYCLE", version: 1, lock: "DEADLOCK CYCLE!", edge: { from: 2, to: 1, type: "wait", label: "T2 waits on T1" } },
                    { step: 5, txn: 2, action: "ABORT (ERROR 1213)", sql: "MySQL ERROR 1213: Deadlock found when trying to get lock; try restarting transaction.", detail: "Engine kills T2 to break cycle! T2 transaction aborted without recovery.", t1Local: "Unblocked", t2Local: "ABORTED (Error 1213)", dbBalance: "T2 Aborted", version: 1, lock: "T2 Released", edge: null }
                ],
                finalVerdict: {
                    isBug: true,
                    expected: "Both Transactions Succeed",
                    actual: "Transaction 2 Aborted / Crushed",
                    loss: "TRANSACTION ABORT EXCEPTION",
                    msg: "DEADLOCK CYCLE TRIGGERED! Two transactions froze in cross-resource locking dependency. T2 was violently aborted."
                }
            },
            safe: {
                label: "Solve: DFS Cycle Detection + Auto-Retry",
                badgeClass: "bg-emerald-950 text-emerald-300 border-emerald-800",
                buttonClass: "bg-emerald-600 hover:bg-emerald-500",
                steps: [
                    { step: 1, txn: 1, action: "LOCK A", sql: "SELECT * FROM accounts WHERE id = 1 FOR UPDATE;", detail: "T1 locks Account 1", t1Local: "Holds Lock(Acc1)", t2Local: "-", dbBalance: "Acc1: T1", version: 1, lock: "Acc1: T1", edge: null },
                    { step: 2, txn: 2, action: "LOCK B", sql: "SELECT * FROM accounts WHERE id = 2 FOR UPDATE;", detail: "T2 locks Account 2", t1Local: "Holds Lock(Acc1)", t2Local: "Holds Lock(Acc2)", dbBalance: "Acc1: T1, Acc2: T2", version: 1, lock: "Acc1: T1, Acc2: T2", edge: null },
                    { step: 3, txn: 1, action: "REQUEST B", sql: "SELECT * FROM accounts WHERE id = 2 FOR UPDATE;", detail: "T1 requests Account 2 -> Enters wait queue", t1Local: "WAITING on Acc2", t2Local: "Holds Lock(Acc2)", dbBalance: "Acc1: T1, Acc2: T2", version: 1, lock: "T1 waits for T2", edge: { from: 1, to: 2, type: "wait", label: "T1 waits on T2" } },
                    { step: 4, txn: 2, action: "DETECT & AUTO-RESOLVE", sql: "LockManager: DFS Cycle Caught T1->T2->T1. Rolling back T2 gracefully.", detail: "DBGuard auto-retry intercepts deadlock, cleanly rolls back T2, freeing T1!", t1Local: "Resuming...", t2Local: "Victim Rollback", dbBalance: "T2 Rolled back", version: 1, lock: "T2 released locks", edge: null },
                    { step: 5, txn: 1, action: "T1 COMPLETES", sql: "UPDATE accounts SET balance = balance - 100; COMMIT;", detail: "T1 finishes both operations and commits safely!", t1Local: "COMMITTED", t2Local: "Backoff (50ms)", dbBalance: "T1 Committed", version: 2, lock: "All Released", edge: null },
                    { step: 6, txn: 2, action: "RETRY HANDLER (AUTO)", sql: "RETRY Txn 2 with Exponential Backoff -> Acquires Locks -> COMMITS!", detail: "Retry Handler awakens T2, acquires both locks sequentially, and completes!", t1Local: "COMMITTED", t2Local: "COMMITTED (Retry #1)", dbBalance: "Both Committed Successfully", version: 3, lock: "None", edge: null }
                ],
                finalVerdict: {
                    isBug: false,
                    expected: "Both Transactions Succeed",
                    actual: "Both Transactions Succeeded",
                    loss: "0 Aborted Transactions",
                    msg: "PROBLEM SOLVED! Wait-for graph DFS cycle detector caught conflict, rolled back victim, and completed on retry with zero human intervention!"
                }
            }
        }
    }
};

let LiveSimState = {
    scenarioKey: "lost_update",
    modeKey: "unsafe",
    currentStep: 0,
    isPlaying: false,
    timer: null
};

function initLiveSimulator() {
    renderScenarioButtons();
    renderModeButtons();
    renderStepView();

    // Controls
    document.getElementById("btn-sim-reset")?.addEventListener("click", resetSim);
    document.getElementById("btn-sim-prev")?.addEventListener("click", prevSimStep);
    document.getElementById("btn-sim-next")?.addEventListener("click", nextSimStep);
    document.getElementById("btn-sim-play")?.addEventListener("click", toggleSimPlay);
}

function renderScenarioButtons() {
    const container = document.getElementById("sim-scenario-selector");
    if (!container) return;

    container.innerHTML = Object.entries(LIVE_SCENARIOS).map(([key, scn]) => {
        const isSelected = key === LiveSimState.scenarioKey;
        const borderClass = isSelected ? "border-cyan-500 bg-cyan-950/40 text-cyan-200" : "border-gray-800 bg-gray-900/60 text-gray-300 hover:border-gray-700";
        return `
            <button onclick="selectLiveScenario('${key}')" 
                    class="p-3 rounded-xl border text-left transition flex flex-col justify-between ${borderClass}">
                <div>
                    <span class="text-[10px] font-mono font-bold text-gray-400 block mb-1">${scn.category}</span>
                    <h4 class="font-bold text-xs text-gray-100">${scn.title}</h4>
                </div>
            </button>
        `;
    }).join("");
}

function renderModeButtons() {
    const container = document.getElementById("sim-mode-selector");
    if (!container) return;

    const currentScenario = LIVE_SCENARIOS[LiveSimState.scenarioKey];
    container.innerHTML = Object.entries(currentScenario.modes).map(([mKey, mode]) => {
        const isSelected = mKey === LiveSimState.modeKey;
        const activeClass = isSelected ? `${mode.buttonClass} text-white font-bold shadow-lg` : "bg-gray-900 text-gray-300 border border-gray-800 hover:bg-gray-800";
        return `
            <button onclick="setLiveMode('${mKey}')" 
                    class="px-4 py-2 rounded-xl text-xs transition flex items-center gap-1.5 ${activeClass}">
                ${mode.label}
            </button>
        `;
    }).join("");
}

window.selectLiveScenario = function(key) {
    stopSimPlay();
    LiveSimState.scenarioKey = key;
    LiveSimState.modeKey = "unsafe"; // Default to unsafe to show problem first!
    LiveSimState.currentStep = 0;
    renderScenarioButtons();
    renderModeButtons();
    renderStepView();
};

window.setLiveMode = function(mKey) {
    stopSimPlay();
    LiveSimState.modeKey = mKey;
    LiveSimState.currentStep = 0;
    renderModeButtons();
    renderStepView();
};

function resetSim() {
    stopSimPlay();
    LiveSimState.currentStep = 0;
    renderStepView();
}

function nextSimStep() {
    const modeData = LIVE_SCENARIOS[LiveSimState.scenarioKey].modes[LiveSimState.modeKey];
    if (LiveSimState.currentStep < modeData.steps.length) {
        LiveSimState.currentStep++;
        renderStepView();
    } else {
        stopSimPlay();
    }
}

function prevSimStep() {
    if (LiveSimState.currentStep > 0) {
        LiveSimState.currentStep--;
        renderStepView();
    }
}

function toggleSimPlay() {
    if (LiveSimState.isPlaying) {
        stopSimPlay();
    } else {
        LiveSimState.isPlaying = true;
        const playBtn = document.getElementById("btn-sim-play");
        if (playBtn) playBtn.innerHTML = `<i data-lucide="pause" class="w-4 h-4"></i> Pause`;
        if (window.lucide) window.lucide.createIcons();

        LiveSimState.timer = setInterval(() => {
            const modeData = LIVE_SCENARIOS[LiveSimState.scenarioKey].modes[LiveSimState.modeKey];
            if (LiveSimState.currentStep < modeData.steps.length) {
                LiveSimState.currentStep++;
                renderStepView();
            } else {
                stopSimPlay();
            }
        }, 600); // Snappy 600ms step speed!
    }
}

function stopSimPlay() {
    LiveSimState.isPlaying = false;
    if (LiveSimState.timer) clearInterval(LiveSimState.timer);
    LiveSimState.timer = null;
    const playBtn = document.getElementById("btn-sim-play");
    if (playBtn) playBtn.innerHTML = `<i data-lucide="play" class="w-4 h-4"></i> Auto Play`;
    if (window.lucide) window.lucide.createIcons();
}

function renderStepView() {
    const scn = LIVE_SCENARIOS[LiveSimState.scenarioKey];
    const mode = scn.modes[LiveSimState.modeKey];
    const totalSteps = mode.steps.length;
    const curIdx = LiveSimState.currentStep; // 0 means initial state

    // Update Counter
    const badge = document.getElementById("sim-step-badge");
    if (badge) badge.textContent = `Step ${curIdx} of ${totalSteps}`;
    
    // Description Header
    const titleElem = document.getElementById("sim-scenario-title");
    if (titleElem) titleElem.textContent = scn.title;
    const descElem = document.getElementById("sim-scenario-desc");
    if (descElem) descElem.textContent = scn.description;

    // Determine current active step object (or initial state)
    let currentStepObj = curIdx > 0 ? mode.steps[curIdx - 1] : null;

    // Database Ledger State Display
    const ledgerResource = document.getElementById("sim-ledger-resource");
    const ledgerBalance = document.getElementById("sim-ledger-balance");
    const ledgerVersion = document.getElementById("sim-ledger-version");
    const ledgerLock = document.getElementById("sim-ledger-lock");

    if (ledgerResource) ledgerResource.textContent = scn.initialState.resource;
    if (ledgerBalance) ledgerBalance.textContent = currentStepObj ? (typeof currentStepObj.dbBalance === 'number' ? `$${currentStepObj.dbBalance.toFixed(2)}` : currentStepObj.dbBalance) : (typeof scn.initialState.balance === 'number' ? `$${scn.initialState.balance.toFixed(2)}` : scn.initialState.balance);
    if (ledgerVersion) ledgerVersion.textContent = `v${currentStepObj ? currentStepObj.version : scn.initialState.version}`;
    if (ledgerLock) ledgerLock.textContent = currentStepObj ? currentStepObj.lock : scn.initialState.lockOwner;

    // Sessions Steps List
    renderSessionStatements("t1", mode.steps.filter(s => s.txn === 1), curIdx);
    renderSessionStatements("t2", mode.steps.filter(s => s.txn === 2), curIdx);

    // Dynamic Graph
    renderLiveSVGGraph(mode.steps.slice(0, curIdx));

    // Final Verdict Banner
    const banner = document.getElementById("sim-verdict-banner");
    if (curIdx === totalSteps) {
        const v = mode.finalVerdict;
        if (v.isBug) {
            banner.className = "p-5 rounded-2xl border border-rose-800 bg-rose-950/60 mb-6 flex items-center justify-between gap-4";
            banner.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="p-2.5 rounded-xl bg-rose-900 text-rose-300 border border-rose-700">
                        <i data-lucide="alert-octagon" class="w-7 h-7"></i>
                    </div>
                    <div>
                        <span class="text-[10px] font-mono font-extrabold uppercase px-2 py-0.5 rounded bg-rose-900/80 text-rose-300 border border-rose-700">ANOMALY TRIGGERED (UNSAFE)</span>
                        <h3 class="font-extrabold text-base text-rose-200 mt-1">${v.msg}</h3>
                        <p class="text-xs text-rose-300/90 font-mono mt-0.5">Expected: ${v.expected} | Actual: ${v.actual} &rarr; <span class="font-bold underline text-rose-200">${v.loss}</span></p>
                    </div>
                </div>
                <button onclick="setLiveMode('${Object.keys(scn.modes).find(m => m !== 'unsafe')}')" 
                        class="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg transition flex items-center gap-1.5 whitespace-nowrap">
                    <i data-lucide="shield-check" class="w-4 h-4"></i> Switch to Safe Mode & Solve It
                </button>
            `;
        } else {
            banner.className = "p-5 rounded-2xl border border-emerald-800 bg-emerald-950/60 mb-6 flex items-center justify-between gap-4";
            banner.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="p-2.5 rounded-xl bg-emerald-900 text-emerald-300 border border-emerald-700">
                        <i data-lucide="check-circle-2" class="w-7 h-7"></i>
                    </div>
                    <div>
                        <span class="text-[10px] font-mono font-extrabold uppercase px-2 py-0.5 rounded bg-emerald-900/80 text-emerald-300 border border-emerald-700">ANOMALY PREVENTED (SAFE)</span>
                        <h3 class="font-extrabold text-base text-emerald-200 mt-1">${v.msg}</h3>
                        <p class="text-xs text-emerald-300/90 font-mono mt-0.5">Expected: ${v.expected} | Actual: ${v.actual} &rarr; <span class="font-bold text-emerald-200">${v.loss}</span></p>
                    </div>
                </div>
                <button onclick="setLiveMode('unsafe')" 
                        class="px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-lg transition flex items-center gap-1.5 whitespace-nowrap">
                    <i data-lucide="refresh-cw" class="w-4 h-4"></i> Re-Trigger Problem in Unsafe Mode
                </button>
            `;
        }
    } else {
        banner.className = "p-4 rounded-xl border border-gray-800 bg-gray-900/50 mb-6 flex items-center justify-between";
        banner.innerHTML = `
            <div class="flex items-center gap-2 text-xs text-gray-300 font-mono">
                <i data-lucide="info" class="w-4 h-4 text-cyan-400"></i>
                <span>Playback active: Click <strong class="text-cyan-400">"Next Step"</strong> or <strong class="text-emerald-400">"Auto Play"</strong> to step through transactions.</span>
            </div>
            <span class="text-xs text-gray-400 font-mono">${curIdx} / ${totalSteps} Operations Executed</span>
        `;
    }

    if (window.lucide) window.lucide.createIcons();
}

function renderSessionStatements(sessionTag, txnSteps, curGlobalStep) {
    const container = document.getElementById(`sim-${sessionTag}-steps`);
    if (!container) return;

    container.innerHTML = txnSteps.map(s => {
        const isPast = s.step <= curGlobalStep;
        const isCurrent = s.step === curGlobalStep;
        
        let statusBadge = "";
        let borderHighlight = "border-gray-800/80 bg-gray-950/60";

        if (isCurrent) {
            borderHighlight = "border-cyan-400 bg-cyan-950/30 shadow-lg shadow-cyan-500/10";
            statusBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800 animate-pulse">ACTIVE STEP</span>`;
        } else if (isPast) {
            statusBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">DONE</span>`;
        } else {
            statusBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] text-gray-500 font-mono">PENDING</span>`;
        }

        const isBlocked = s.action.includes("BLOCKED") || s.action.includes("WAIT");
        const actionColor = isBlocked ? "text-amber-400" : s.action.includes("OVERWRITE") || s.action.includes("CONFLICT") ? "text-rose-400 font-bold" : "text-cyan-300 font-semibold";

        return `
            <div class="p-2.5 rounded-xl border text-xs font-mono transition mb-2 ${borderHighlight}">
                <div class="flex items-center justify-between mb-1">
                    <span class="text-[11px] font-bold ${actionColor}">Step ${s.step}: ${s.action}</span>
                    ${statusBadge}
                </div>
                <div class="p-1.5 rounded bg-black/60 text-gray-200 text-[11px] mb-1 font-mono">${s.sql}</div>
                <div class="text-[10px] text-gray-400 font-sans">${s.detail}</div>
            </div>
        `;
    }).join("");
}

function renderLiveSVGGraph(executedSteps) {
    const svg = document.getElementById("sim-graph-svg");
    if (!svg) return;

    // Filter edges from executed steps
    const edges = executedSteps.filter(s => s.edge !== null).map(s => s.edge);

    let edgeMarkup = "";
    edges.forEach((e, idx) => {
        const is1to2 = e.from === 1 && e.to === 2;
        const color = e.type === 'wait' ? '#f59e0b' : e.type === 'ww' ? '#f43f5e' : '#10b981';
        const startX = is1to2 ? 110 : 290;
        const endX = is1to2 ? 290 : 110;
        const y = 80 + (idx * 30);

        edgeMarkup += `
            <g>
                <path d="M ${startX} ${y} C 200 ${y - 25}, 200 ${y - 25}, ${endX} ${y}" 
                      fill="none" stroke="${color}" stroke-width="2.5" marker-end="url(#live-arrow-${e.type})"/>
                <text x="200" y="${y - 12}" fill="${color}" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">
                    ${e.type.toUpperCase()}: ${e.label}
                </text>
            </g>
        `;
    });

    svg.innerHTML = `
        <defs>
            <marker id="live-arrow-wait" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><polygon points="0 0, 8 4, 0 8" fill="#f59e0b"/></marker>
            <marker id="live-arrow-ww" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><polygon points="0 0, 8 4, 0 8" fill="#f43f5e"/></marker>
            <marker id="live-arrow-wr" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><polygon points="0 0, 8 4, 0 8" fill="#10b981"/></marker>
            <marker id="live-arrow-rw" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><polygon points="0 0, 8 4, 0 8" fill="#a855f7"/></marker>
        </defs>

        <!-- Txn 1 Node -->
        <circle cx="80" cy="95" r="30" fill="#164e63" stroke="#06b6d4" stroke-width="2.5"/>
        <text x="80" y="100" fill="#cffafe" font-size="12" font-weight="bold" font-family="sans-serif" text-anchor="middle">Txn 1</text>

        <!-- Txn 2 Node -->
        <circle cx="320" cy="95" r="30" fill="#3b0764" stroke="#a855f7" stroke-width="2.5"/>
        <text x="320" y="100" fill="#f3e8ff" font-size="12" font-weight="bold" font-family="sans-serif" text-anchor="middle">Txn 2</text>

        ${edgeMarkup}
    `;
}

// -------------------------------------------------------------
// Tab 1: Anomaly Pattern Catalog
// -------------------------------------------------------------
async function initPatternCatalog() {
    const listContainer = document.getElementById("pattern-list-container");
    const filterSelect = document.getElementById("pattern-filter-iso");
    const countBadge = document.getElementById("pattern-count-badge");

    async function loadPatterns(isoFilter = "") {
        try {
            const url = isoFilter ? `/api/aptrans/patterns?isolation_level=${encodeURIComponent(isoFilter)}` : "/api/aptrans/patterns";
            const res = await fetch(url);
            const data = await res.json();
            APState.patterns = data.patterns;
            if (countBadge) countBadge.textContent = `${data.total_patterns} Patterns`;
            renderPatternCards(data.patterns);
        } catch (err) {
            if (listContainer) listContainer.innerHTML = `<div class="p-4 text-red-400">Failed to load patterns: ${err.message}</div>`;
        }
    }

    if (filterSelect) {
        filterSelect.addEventListener("change", (e) => {
            loadPatterns(e.target.value);
        });
    }

    await loadPatterns();
}

function renderPatternCards(patterns) {
    const listContainer = document.getElementById("pattern-list-container");
    if (!listContainer) return;

    if (!patterns.length) {
        listContainer.innerHTML = `<div class="col-span-3 p-8 text-center text-gray-500">No patterns matching selected filter.</div>`;
        return;
    }

    listContainer.innerHTML = patterns.map(p => {
        const isCanonical = p.pattern_id.startsWith("C-");
        const badgeColor = isCanonical ? "bg-amber-950 text-amber-300 border-amber-800" : "bg-cyan-950 text-cyan-300 border-cyan-800";
        const disallowedBadges = p.disallowed_levels.map(lvl => 
            `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-950 text-rose-300 border border-rose-800/60">${lvl}</span>`
        ).join(" ");

        return `
            <div class="glass-panel p-4 rounded-xl border border-gray-800 hover:border-cyan-500/50 transition cursor-pointer flex flex-col justify-between"
                 onclick="selectPatternForGeneration('${p.pattern_id}')">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-2">
                        <span class="px-2 py-0.5 rounded text-[11px] font-mono font-bold ${badgeColor} border">${p.pattern_id}</span>
                        <div class="flex flex-wrap gap-1">${disallowedBadges}</div>
                    </div>
                    <h3 class="font-bold text-sm text-gray-100">${p.name}</h3>
                    <div class="mt-2 p-2 rounded bg-gray-900/80 font-mono text-xs text-cyan-300 tracking-wide break-all border border-gray-800">
                        ${p.raw_pattern}
                    </div>
                    <p class="mt-2 text-xs text-gray-400 line-clamp-2">${p.description || "Systematic two-transaction concurrency anomaly pattern."}</p>
                </div>
                <div class="mt-4 pt-3 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-gray-400">
                    <span class="font-mono">Ops: ${p.cstr3 ? p.cstr3.length : 0} steps</span>
                    <span class="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1">
                        Synthesize <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
                    </span>
                </div>
            </div>
        `;
    }).join("");

    if (window.lucide) {
        window.lucide.createIcons();
    }
}

window.selectPatternForGeneration = function(patternId) {
    APState.selectedPatternId = patternId;
    const selectElem = document.getElementById("gen-pattern-select");
    if (selectElem) selectElem.value = patternId;
    switchTab("generator");
    triggerGeneration();
};

// -------------------------------------------------------------
// Tab 2: Algorithm 1 Transaction Generator
// -------------------------------------------------------------
function initGenerator() {
    const patternSelect = document.getElementById("gen-pattern-select");
    const btnGenerate = document.getElementById("btn-run-generate");
    const btnSendToExec = document.getElementById("btn-send-to-exec");

    fetch("/api/aptrans/patterns")
        .then(res => res.json())
        .then(data => {
            if (patternSelect) {
                patternSelect.innerHTML = data.patterns.map(p => 
                    `<option value="${p.pattern_id}">[${p.pattern_id}] ${p.name} (${p.raw_pattern})</option>`
                ).join("");
                if (APState.selectedPatternId) {
                    patternSelect.value = APState.selectedPatternId;
                }
            }
        });

    if (btnGenerate) btnGenerate.addEventListener("click", triggerGeneration);
    if (btnSendToExec) {
        btnSendToExec.addEventListener("click", () => {
            switchTab("scheduler");
            triggerExecution();
        });
    }
}

async function triggerGeneration() {
    const patternId = document.getElementById("gen-pattern-select")?.value || "C-LU";
    const isoLevel = document.getElementById("gen-iso-select")?.value || "REPEATABLE READ";
    const useSnapshot = document.getElementById("gen-snapshot-check")?.checked || false;

    try {
        const res = await fetch("/api/aptrans/generate", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                pattern_id: patternId,
                isolation_level: isoLevel,
                use_consistent_snapshot: useSnapshot
            })
        });
        const caseData = await res.json();
        APState.currentCase = caseData;
        renderGeneratedTransactions(caseData);
    } catch (err) {
        alert("Generation failed: " + err.message);
    }
}

function renderGeneratedTransactions(caseData) {
    document.getElementById("gen-pattern-badge").textContent = `${caseData.pattern_id}: ${caseData.pattern_name}`;
    document.getElementById("gen-formula-badge").textContent = caseData.raw_pattern;
    document.getElementById("gen-disallowed-badge").textContent = `Disallowed in: ${caseData.disallowed_levels.join(", ")}`;

    const t1Lines = [
        `-- Transaction 1 (${caseData.isolation_level})`,
        `SET TRANSACTION ISOLATION LEVEL ${caseData.isolation_level};`,
        caseData.use_consistent_snapshot ? `START TRANSACTION WITH CONSISTENT SNAPSHOT;` : `BEGIN;`,
        ...(caseData.txn_statements[1] || []).map(s => s.sql)
    ];
    document.getElementById("gen-t1-code").textContent = t1Lines.join("\n");

    const t2Lines = [
        `-- Transaction 2 (${caseData.isolation_level})`,
        `SET TRANSACTION ISOLATION LEVEL ${caseData.isolation_level};`,
        caseData.use_consistent_snapshot ? `START TRANSACTION WITH CONSISTENT SNAPSHOT;` : `BEGIN;`,
        ...(caseData.txn_statements[2] || []).map(s => s.sql)
    ];
    document.getElementById("gen-t2-code").textContent = t2Lines.join("\n");

    const schedTable = document.getElementById("gen-schedule-table");
    schedTable.innerHTML = (caseData.global_schedule || []).map((step, idx) => `
        <tr class="border-b border-gray-800 text-xs hover:bg-gray-800/40 font-mono">
            <td class="py-2 px-3 text-gray-400">Step ${String(idx + 1).padStart(2, '0')}</td>
            <td class="py-2 px-3">
                <span class="px-2 py-0.5 rounded font-bold ${step.txn_id === 1 ? 'bg-cyan-950 text-cyan-300 border border-cyan-800' : 'bg-purple-950 text-purple-300 border border-purple-800'}">
                    Txn ${step.txn_id}
                </span>
            </td>
            <td class="py-2 px-3 font-semibold text-amber-300">${step.notation}</td>
            <td class="py-2 px-3 text-gray-200">${step.sql}</td>
        </tr>
    `).join("");
}

// -------------------------------------------------------------
// Tab 3: Algorithm 2 Execution Engine & Scheduler
// -------------------------------------------------------------
function initScheduler() {
    const btnRunExec = document.getElementById("btn-run-execution");
    if (btnRunExec) btnRunExec.addEventListener("click", triggerExecution);
}

async function triggerExecution() {
    const patternId = document.getElementById("gen-pattern-select")?.value || "C-LU";
    const isoLevel = document.getElementById("gen-iso-select")?.value || "REPEATABLE READ";
    const useSnapshot = document.getElementById("gen-snapshot-check")?.checked || false;

    try {
        const res = await fetch("/api/aptrans/execute", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                pattern_id: patternId,
                isolation_level: isoLevel,
                use_consistent_snapshot: useSnapshot
            })
        });
        const result = await res.json();
        APState.currentCase = result.test_case;
        APState.currentTrace = result.trace;
        APState.currentReport = result.report;
        renderExecutionTrace(result);
    } catch (err) {
        alert("Execution failed: " + err.message);
    }
}

function renderExecutionTrace(data) {
    const trace = data.trace;
    const report = data.report;

    const timelineContainer = document.getElementById("exec-timeline-container");
    timelineContainer.innerHTML = trace.steps.map(step => {
        const isTxn1 = step.txn_id === 1;
        const borderClass = isTxn1 ? "border-cyan-500/40" : "border-purple-500/40";
        const statusClass = step.status === "SUCCESS" ? "text-emerald-400 bg-emerald-950/60 border-emerald-800" :
                            step.status === "BLOCKED" ? "text-amber-400 bg-amber-950/60 border-amber-800 badge-lock-wait" :
                            "text-rose-400 bg-rose-950/60 border-rose-800";

        let resultSummary = "";
        if (step.read_rows && step.read_rows.length) {
            resultSummary = `<div class="mt-2 text-[11px] text-gray-300 bg-gray-900 p-2 rounded border border-gray-800 font-mono">
                <span class="text-cyan-400">Read:</span> ${JSON.stringify(step.read_rows)}
            </div>`;
        }
        if (step.written_rows && step.written_rows.length) {
            resultSummary = `<div class="mt-2 text-[11px] text-gray-300 bg-gray-900 p-2 rounded border border-gray-800 font-mono">
                <span class="text-emerald-400">Written:</span> ${JSON.stringify(step.written_rows)}
            </div>`;
        }

        return `
            <div class="glass-panel p-3.5 rounded-xl border ${borderClass} relative mb-3">
                <div class="flex items-center justify-between gap-2">
                    <div class="flex items-center gap-2">
                        <span class="px-2 py-0.5 rounded text-xs font-mono font-bold ${isTxn1 ? 'bg-cyan-950 text-cyan-300' : 'bg-purple-950 text-purple-300'} border border-gray-800">
                            Txn ${step.txn_id}
                        </span>
                        <span class="font-mono text-xs font-bold text-amber-300">${step.notation}</span>
                        <span class="text-xs text-gray-400 font-mono">Step ${step.step_idx}</span>
                    </div>
                    <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${statusClass}">
                        ${step.status}
                    </span>
                </div>
                <div class="mt-1.5 font-mono text-xs text-gray-100 bg-gray-950/70 p-2 rounded border border-gray-800/80">
                    ${step.sql}
                </div>
                ${resultSummary}
            </div>
        `;
    }).join("");

    const logContainer = document.getElementById("exec-logs-table");
    const combinedLogs = trace.wal_observer_log || trace.database_log || [];
    logContainer.innerHTML = combinedLogs.map(l => `
        <tr class="border-b border-gray-800 text-xs font-mono hover:bg-gray-800/30">
            <td class="py-2 px-3 text-gray-400">${l.log_id}</td>
            <td class="py-2 px-3 text-cyan-300 font-semibold">${l.operation_type}</td>
            <td class="py-2 px-3">Txn ${l.txn_id}</td>
            <td class="py-2 px-3 text-gray-300">row_id: ${l.row_id}</td>
            <td class="py-2 px-3 text-amber-300">v${l.version}</td>
            <td class="py-2 px-3 text-gray-400">${l.old_c0 ?? 'NULL'}</td>
            <td class="py-2 px-3 text-emerald-400 font-bold">${l.new_c0}</td>
            <td class="py-2 px-3">
                <span class="px-1.5 py-0.5 rounded text-[10px] ${l.status === 'ROLLED_BACK' ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-emerald-950 text-emerald-300 border border-emerald-800'}">
                    ${l.status || 'COMMITTED'}
                </span>
            </td>
        </tr>
    `).join("");

    renderDetectorReport(report);
}

// -------------------------------------------------------------
// Tab 4: Dynamic Dependency Graph & Two-Phase Bug Detector
// -------------------------------------------------------------
function initDetector() {}

function renderDetectorReport(report) {
    if (!report) return;

    const verdictElem = document.getElementById("detector-verdict-banner");
    if (report.is_bug) {
        verdictElem.className = "p-4 rounded-xl border border-rose-800 bg-rose-950/40 text-rose-200 mb-6";
        verdictElem.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-rose-900/60 text-rose-300 border border-rose-700">
                    <i data-lucide="alert-triangle" class="w-6 h-6"></i>
                </div>
                <div>
                    <h3 class="font-extrabold text-base text-rose-300">TRANSACTION BUG CONFIRMED [${report.verdict}]</h3>
                    <p class="text-xs text-rose-200/90 mt-0.5">${report.anomaly_details || 'Anomaly pattern prohibited under current isolation level.'}</p>
                </div>
            </div>
        `;
    } else {
        verdictElem.className = "p-4 rounded-xl border border-emerald-800 bg-emerald-950/40 text-emerald-200 mb-6";
        verdictElem.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="p-2 rounded-lg bg-emerald-900/60 text-emerald-300 border border-emerald-700">
                    <i data-lucide="check-circle" class="w-6 h-6"></i>
                </div>
                <div>
                    <h3 class="font-extrabold text-base text-emerald-300">ISOLATION INVARIANT PRESERVED [PASS]</h3>
                    <p class="text-xs text-emerald-200/90 mt-0.5">Execution history satisfied formal serializability / isolation criteria for ${report.isolation_level}.</p>
                </div>
            </div>
        `;
    }

    const explicitElem = document.getElementById("detector-explicit-summary");
    const filtered = report.filtered_errors || [];
    explicitElem.innerHTML = filtered.length ? 
        filtered.map(f => `<div class="p-2 rounded bg-gray-900 border border-gray-800 text-xs text-gray-400 font-mono mb-1.5"><span class="text-amber-400 font-bold">Filtered:</span> ${f}</div>`).join("") :
        `<div class="p-3 text-xs text-gray-400 font-mono">Zero crashes, assertion failures, or synthetic syntax errors detected. Non-isolation errors successfully filtered.</div>`;

    renderGraphVisualization(report.graph);
    if (window.lucide) window.lucide.createIcons();
}

function renderGraphVisualization(graph) {
    const container = document.getElementById("detector-graph-svg");
    if (!graph || !graph.edges) {
        container.innerHTML = `<text x="250" y="100" fill="#6b7280" text-anchor="middle" font-size="12">No dependencies recorded yet</text>`;
        return;
    }

    const edges = graph.edges;
    let edgeLines = "";

    edges.forEach((edge, idx) => {
        const isT1toT2 = edge.from_txn === 1 && edge.to_txn === 2;
        const color = edge.type === 'ww' ? '#f59e0b' : edge.type === 'wr' ? '#10b981' : '#a855f7';
        const yOffset = 70 + (idx * 28);
        const startX = isT1toT2 ? 140 : 360;
        const endX = isT1toT2 ? 360 : 140;

        edgeLines += `
            <g>
                <path d="M ${startX} ${yOffset} C ${isT1toT2 ? 250 : 250} ${yOffset - 30}, ${isT1toT2 ? 250 : 250} ${yOffset - 30}, ${endX} ${yOffset}" 
                      fill="none" stroke="${color}" stroke-width="2.5" marker-end="url(#arrow-${edge.type})"/>
                <text x="250" y="${yOffset - 18}" fill="${color}" font-size="11" font-family="monospace" font-weight="bold" text-anchor="middle">
                    ${edge.type.toUpperCase()} [row:${edge.row_id}, v${edge.version}]
                </text>
            </g>
        `;
    });

    container.innerHTML = `
        <defs>
            <marker id="arrow-ww" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><polygon points="0 0, 8 4, 0 8" fill="#f59e0b"/></marker>
            <marker id="arrow-wr" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><polygon points="0 0, 8 4, 0 8" fill="#10b981"/></marker>
            <marker id="arrow-rw" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><polygon points="0 0, 8 4, 0 8" fill="#a855f7"/></marker>
        </defs>

        <circle cx="100" cy="120" r="36" fill="#164e63" stroke="#06b6d4" stroke-width="2.5"/>
        <text x="100" y="125" fill="#cffafe" font-size="14" font-weight="bold" font-family="sans-serif" text-anchor="middle">Txn 1</text>

        <circle cx="400" cy="120" r="36" fill="#3b0764" stroke="#a855f7" stroke-width="2.5"/>
        <text x="400" y="125" fill="#f3e8ff" font-size="14" font-weight="bold" font-family="sans-serif" text-anchor="middle">Txn 2</text>

        ${edgeLines}
    `;

    const edgeListElem = document.getElementById("detector-edges-list");
    edgeListElem.innerHTML = edges.map(e => `
        <div class="flex items-center justify-between p-2 rounded bg-gray-900 border border-gray-800 text-xs font-mono mb-1.5">
            <span class="font-bold ${e.type === 'ww' ? 'text-amber-400' : e.type === 'wr' ? 'text-emerald-400' : 'text-purple-400'}">
                ${e.type.toUpperCase()} Dependency:
            </span>
            <span class="text-gray-300">T${e.from_txn} &rarr; T${e.to_txn} (row_id: ${e.row_id}, v:${e.version})</span>
        </div>
    `).join("") || `<div class="text-xs text-gray-500 font-mono">No dependency edges.</div>`;
}

// -------------------------------------------------------------
// Tab 5: Real-World Case Studies
// -------------------------------------------------------------
function initCaseStudies() {
    [1, 2, 3].forEach(id => {
        const btn = document.getElementById(`btn-case-study-${id}`);
        if (btn) btn.addEventListener("click", () => runCaseStudy(id));
    });
}

async function runCaseStudy(id) {
    try {
        const res = await fetch(`/api/aptrans/case-studies/${id}`);
        const data = await res.json();
        
        const container = document.getElementById("case-study-details-container");
        container.classList.remove("hidden");
        
        document.getElementById("cs-title").textContent = `${data.bug_id} (${data.dbms})`;
        document.getElementById("cs-iso-badge").textContent = data.isolation_level;
        document.getElementById("cs-pattern-badge").textContent = data.pattern;
        document.getElementById("cs-verdict-badge").textContent = data.report.verdict;
        document.getElementById("cs-explanation").textContent = data.academic_explanation;

        const stepsElem = document.getElementById("cs-steps-list");
        stepsElem.innerHTML = data.sql_steps.map(s => `
            <div class="flex items-center gap-3 p-2 rounded bg-gray-900 border border-gray-800 text-xs font-mono mb-1">
                <span class="text-gray-400 w-12">Step ${s.step}</span>
                <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${s.txn === 1 ? 'bg-cyan-950 text-cyan-300' : 'bg-purple-950 text-purple-300'} border border-gray-700">Txn ${s.txn}</span>
                <span class="text-amber-300 font-semibold w-24">${s.notation}</span>
                <span class="text-gray-200">${s.sql}</span>
            </div>
        `).join("");

        container.scrollIntoView({behavior: "smooth"});
        if (window.lucide) window.lucide.createIcons();
    } catch (err) {
        alert("Case study execution failed: " + err.message);
    }
}

// -------------------------------------------------------------
// Tab 6: Benchmark & Ablation Lab
// -------------------------------------------------------------
async function initBenchmarks() {
    try {
        const res = await fetch("/api/aptrans/benchmarks");
        const data = await res.json();

        const table5Elem = document.getElementById("bench-table-5-body");
        if (table5Elem) {
            table5Elem.innerHTML = data.table_5_bugs.map(b => `
                <tr class="border-b border-gray-800 text-xs font-mono hover:bg-gray-800/30">
                    <td class="py-2.5 px-3 font-bold text-cyan-300">${b.dbms}</td>
                    <td class="py-2.5 px-3 text-gray-200">#${b.bug_id}</td>
                    <td class="py-2.5 px-3">
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">${b.status}</span>
                    </td>
                    <td class="py-2.5 px-3">
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold ${b.severity === 'Critical' ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-amber-950 text-amber-300 border border-amber-800'}">${b.severity}</span>
                    </td>
                    <td class="py-2.5 px-3 font-semibold text-purple-300">${b.isolation_level}</td>
                    <td class="py-2.5 px-3 text-cyan-400 font-mono">${b.pattern}</td>
                    <td class="py-2.5 px-3 text-gray-400 font-sans">${b.summary}</td>
                </tr>
            `).join("");
        }

        const table7Elem = document.getElementById("bench-table-7-body");
        if (table7Elem) {
            table7Elem.innerHTML = data.table_7_ablation.map(a => `
                <tr class="border-b border-gray-800 text-xs font-mono hover:bg-gray-800/30">
                    <td class="py-2.5 px-3 font-bold text-gray-200">${a.method}</td>
                    <td class="py-2.5 px-3 text-center text-cyan-300">${a.mysql}</td>
                    <td class="py-2.5 px-3 text-center text-purple-300">${a.mariadb}</td>
                    <td class="py-2.5 px-3 text-center text-emerald-300">${a.oceanbase}</td>
                    <td class="py-2.5 px-3 text-center font-bold text-amber-300">${a.total}</td>
                    <td class="py-2.5 px-3 text-gray-400 font-sans">${a.description}</td>
                </tr>
            `).join("");
        }
    } catch (err) {
        console.error("Benchmark load failed", err);
    }
}

// -------------------------------------------------------------
// Tab 7: Critique & Fallacies
// -------------------------------------------------------------
async function initCritique() {
    try {
        const res = await fetch("/api/aptrans/critique");
        const data = await res.json();
        const container = document.getElementById("critique-cards-container");
        if (container) {
            container.innerHTML = data.fallacies.map(f => `
                <div class="glass-panel p-5 rounded-xl border border-gray-800 mb-4 hover:border-gray-700 transition">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-rose-950 text-rose-300 border border-rose-800">Fallacy ${f.id}</span>
                        <h3 class="font-extrabold text-sm text-gray-100">${f.title}</h3>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-xs">
                        <div class="p-3 rounded-lg bg-gray-900/80 border border-gray-800">
                            <span class="text-rose-400 font-bold block mb-1">Paper Claim / Foundational Flaw:</span>
                            <p class="text-gray-300">${f.fallacy}</p>
                        </div>
                        <div class="p-3 rounded-lg bg-cyan-950/20 border border-cyan-800/40">
                            <span class="text-cyan-400 font-bold block mb-1">Our Reconstruction's Solution / Update:</span>
                            <p class="text-cyan-200/90">${f.update_implemented}</p>
                        </div>
                    </div>
                </div>
            `).join("");
        }
    } catch (err) {
        console.error("Critique load failed", err);
    }
}

// -------------------------------------------------------------
// Tab 8: DBMS Professor Evaluation
// -------------------------------------------------------------
async function initEvaluation() {
    try {
        const res = await fetch("/api/aptrans/evaluation");
        const data = await res.json();

        const scoreElem = document.getElementById("eval-score-display");
        const verdictElem = document.getElementById("eval-verdict-display");
        if (scoreElem) scoreElem.textContent = `${data.normalized_score} / 10.0`;
        if (verdictElem) verdictElem.textContent = data.verdict;

        const rubricContainer = document.getElementById("eval-rubric-cards");
        if (rubricContainer) {
            rubricContainer.innerHTML = data.rubric.map(r => `
                <div class="glass-panel p-4 rounded-xl border border-gray-800 flex items-center justify-between gap-4">
                    <div class="flex-1">
                        <div class="flex items-center gap-2">
                            <h4 class="font-bold text-sm text-gray-100">${r.dimension}</h4>
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">${r.status}</span>
                        </div>
                        <p class="text-xs text-gray-400 mt-1">${r.comments}</p>
                    </div>
                    <div class="text-right">
                        <div class="font-mono text-base font-extrabold text-cyan-400">${r.score} <span class="text-xs text-gray-500">/ ${r.max}</span></div>
                        <span class="text-[10px] text-gray-500">Weighted 10%</span>
                    </div>
                </div>
            `).join("");
        }
    } catch (err) {
        console.error("Evaluation load failed", err);
    }
}
