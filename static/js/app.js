/**
 * DBGuard Main Application Controller
 */

const DBGuardApp = {
    currentUser: {
        username: "admin",
        role: "ADMIN",
        token: null
    },
    activeTab: "simulator",

    init: async function() {
        this.setupNavigation();
        this.setupRoleSwitcher();
        this.setupScenarioControls();
        await this.refreshAll();
        // Periodic telemetry refresh every 5 seconds
        setInterval(() => this.refreshMetricsAndState(), 5000);
    },

    setupNavigation: function() {
        const navBtns = document.querySelectorAll("[data-nav-tab]");
        navBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                const targetTab = btn.getAttribute("data-nav-tab");
                this.switchTab(targetTab);
            });
        });
    },

    switchTab: function(tabName) {
        this.activeTab = tabName;
        // Update nav buttons
        document.querySelectorAll("[data-nav-tab]").forEach(btn => {
            if (btn.getAttribute("data-nav-tab") === tabName) {
                btn.className = "flex items-center gap-2 px-3.5 py-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 text-xs font-semibold";
            } else {
                btn.className = "flex items-center gap-2 px-3.5 py-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-gray-800 text-xs font-medium transition";
            }
        });

        // Hide all tab panes
        document.querySelectorAll(".tab-pane").forEach(pane => {
            pane.classList.add("hidden");
        });

        // Show active pane
        const activePane = document.getElementById(`tab-${tabName}`);
        if (activePane) activePane.classList.remove("hidden");

        if (tabName === "audit") this.loadAuditLogs();
        if (tabName === "conflicts") this.loadConflictLogs();
        if (tabName === "tables") this.loadSystemTables();
        if (tabName === "rules") this.loadRules();

        if (window.lucide) lucide.createIcons();
    },

    setupRoleSwitcher: function() {
        const selector = document.getElementById("role-selector");
        if (selector) {
            selector.addEventListener("change", async (e) => {
                const role = e.target.value;
                this.currentUser.role = role;
                this.currentUser.username = role.toLowerCase();
                this.showToast(`Switched active persona to ${role}`, "info");
                this.updateRoleBadges();
            });
        }
    },

    updateRoleBadges: function() {
        const badge = document.getElementById("active-role-badge");
        if (badge) {
            badge.textContent = this.currentUser.role;
            if (this.currentUser.role === "ADMIN") {
                badge.className = "px-2 py-0.5 rounded text-xs font-semibold bg-rose-950/80 text-rose-300 border border-rose-600";
            } else if (this.currentUser.role === "AUDITOR") {
                badge.className = "px-2 py-0.5 rounded text-xs font-semibold bg-purple-950/80 text-purple-300 border border-purple-600";
            } else {
                badge.className = "px-2 py-0.5 rounded text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-600";
            }
        }
    },

    setupScenarioControls: function() {
        const scenarioSelect = document.getElementById("scenario-type");
        const modeSelect = document.getElementById("scenario-mode");

        if (scenarioSelect && modeSelect) {
            scenarioSelect.addEventListener("change", (e) => {
                const sc = e.target.value;
                modeSelect.innerHTML = "";
                if (sc === "lost_update") {
                    modeSelect.innerHTML = `
                        <option value="unsafe">Unsafe Mode (Race Condition / Data Loss)</option>
                        <option value="pessimistic">Safe Mode: Pessimistic Locking (SELECT ... FOR UPDATE)</option>
                        <option value="optimistic">Safe Mode: Optimistic Locking (WHERE version = :v)</option>
                        <option value="atomic">Safe Mode: Atomic In-Database Deduction</option>
                    `;
                } else if (sc === "double_booking") {
                    modeSelect.innerHTML = `
                        <option value="unsafe">Unsafe Mode (Race Condition Overwrite)</option>
                        <option value="safe">Safe Mode (Row Lock + UNIQUE Constraint)</option>
                    `;
                } else if (sc === "deadlock") {
                    modeSelect.innerHTML = `
                        <option value="auto_retry">Safe Mode: Cycle Detection + Exponential Auto-Retry</option>
                        <option value="unsafe_deadlock">Unsafe Mode: Abort Victim Transaction (Error 1213)</option>
                    `;
                } else if (sc === "savepoint") {
                    modeSelect.innerHTML = `
                        <option value="default">Multi-step Batch Purchase with Partial Rollback</option>
                    `;
                } else if (sc === "integrity") {
                    modeSelect.innerHTML = `
                        <option value="default">Negative Balance Check (CHECK balance >= 0.00)</option>
                    `;
                }
            });
        }

        const runBtn = document.getElementById("btn-run-simulation");
        if (runBtn) {
            runBtn.addEventListener("click", () => this.executeSelectedScenario());
        }

        const resetBtn = document.getElementById("btn-reset-db");
        if (resetBtn) {
            resetBtn.addEventListener("click", () => this.resetDatabase());
        }
    },

    executeSelectedScenario: async function() {
        const scenario = document.getElementById("scenario-type").value;
        const mode = document.getElementById("scenario-mode").value;
        const runBtn = document.getElementById("btn-run-simulation");

        runBtn.disabled = true;
        runBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Executing Transactions...`;
        if (window.lucide) lucide.createIcons();

        try {
            let res;
            if (scenario === "lost_update") {
                res = await fetch("/api/scenarios/run-lost-update", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: mode, account_id: 1, deduct_t1: 100, deduct_t2: 200 })
                });
            } else if (scenario === "double_booking") {
                res = await fetch("/api/scenarios/run-double-booking", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: mode, ticket_id: 1 })
                });
            } else if (scenario === "deadlock") {
                res = await fetch("/api/scenarios/run-deadlock", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: mode })
                });
            } else if (scenario === "savepoint") {
                res = await fetch("/api/scenarios/run-savepoint", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({})
                });
            } else if (scenario === "integrity") {
                res = await fetch("/api/scenarios/run-integrity-violation", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ account_id: 1, deduct_amount: 1500 })
                });
            }

            const data = await res.json();
            if (res.ok) {
                this.showToast("Simulation completed successfully!", "success");
                window.DBSimulator.renderTimeline(data.timeline || data.steps);
                window.DBSimulator.renderComparison(data);
                await this.refreshMetricsAndState();
            } else {
                this.showToast(data.error || "Scenario execution failed", "error");
            }
        } catch (err) {
            this.showToast(`Error: ${err.message}`, "error");
        } finally {
            runBtn.disabled = false;
            runBtn.innerHTML = `<i data-lucide="play" class="w-4 h-4"></i> Run Simulation`;
            if (window.lucide) lucide.createIcons();
        }
    },

    resetDatabase: async function() {
        if (this.currentUser.role !== "ADMIN") {
            this.showToast("Permission Denied: Only ADMIN can reset the system state.", "error");
            return;
        }

        try {
            const res = await fetch("/api/system/reset", { method: "POST" });
            const data = await res.json();
            if (res.ok) {
                this.showToast(data.message, "success");
                window.DBSimulator.renderTimeline([]);
                window.DBSimulator.renderComparison(null);
                await this.refreshMetricsAndState();
            } else {
                this.showToast(data.error || "Reset failed", "error");
            }
        } catch (e) {
            this.showToast(e.message, "error");
        }
    },

    refreshAll: async function() {
        await this.refreshMetricsAndState();
        this.updateRoleBadges();
    },

    refreshMetricsAndState: async function() {
        try {
            const [metricsRes, stateRes] = await Promise.all([
                fetch("/api/metrics"),
                fetch("/api/system-state")
            ]);
            if (metricsRes.ok) {
                const m = await metricsRes.json();
                document.getElementById("stat-total-tx").textContent = m.total_transactions;
                document.getElementById("stat-conflict-rate").textContent = `${m.conflict_rate_percent}%`;
                document.getElementById("stat-deadlocks").textContent = m.deadlocks_auto_resolved;
                document.getElementById("stat-integrity").textContent = m.integrity_violations_blocked;
            }
            if (stateRes.ok) {
                const s = await stateRes.json();
                this.renderQuickAccounts(s.accounts);
                document.getElementById("stat-engine-mode").textContent = s.db_mode.toUpperCase();
            }
        } catch (err) {
            console.error("Telemetry refresh error:", err);
        }
    },

    renderQuickAccounts: function(accounts) {
        const container = document.getElementById("quick-accounts-container");
        if (!container || !accounts) return;

        container.innerHTML = accounts.map(a => `
            <div class="flex items-center justify-between p-3 rounded-lg bg-gray-900/60 border border-gray-700/60">
                <div>
                    <div class="font-mono font-semibold text-xs text-white">${a.account_number} (${a.holder_name})</div>
                    <div class="text-[11px] text-gray-400">Lock Version: v${a.version}</div>
                </div>
                <div class="text-right">
                    <div class="font-mono font-bold text-sm text-cyan-400">$${Number(a.balance).toFixed(2)}</div>
                    <div class="text-[10px] text-emerald-400 font-medium">InnoDB Active</div>
                </div>
            </div>
        `).join("");
    },

    loadSystemTables: async function() {
        try {
            const res = await fetch("/api/system-state");
            const data = await res.json();

            // Accounts
            const accTbody = document.getElementById("table-accounts-body");
            if (accTbody) {
                accTbody.innerHTML = data.accounts.map(a => `
                    <tr class="border-b border-gray-800 hover:bg-gray-800/40 font-mono text-xs">
                        <td class="p-3 text-gray-300">#${a.account_id}</td>
                        <td class="p-3 text-cyan-300 font-semibold">${a.account_number}</td>
                        <td class="p-3 text-gray-200">${a.holder_name}</td>
                        <td class="p-3 text-emerald-400 font-bold">$${Number(a.balance).toFixed(2)}</td>
                        <td class="p-3 text-purple-300">v${a.version}</td>
                        <td class="p-3 text-gray-400">${a.updated_at}</td>
                    </tr>
                `).join("");
            }

            // Tickets
            const tickTbody = document.getElementById("table-tickets-body");
            if (tickTbody) {
                tickTbody.innerHTML = data.tickets.map(t => {
                    let statusBadge = t.status === "AVAILABLE"
                        ? '<span class="px-2 py-0.5 rounded text-[11px] bg-emerald-950 text-emerald-300 border border-emerald-600">AVAILABLE</span>'
                        : '<span class="px-2 py-0.5 rounded text-[11px] bg-rose-950 text-rose-300 border border-rose-600">BOOKED</span>';
                    return `
                        <tr class="border-b border-gray-800 hover:bg-gray-800/40 font-mono text-xs">
                            <td class="p-3 text-gray-300">#${t.ticket_id}</td>
                            <td class="p-3 text-gray-200">${t.event_name}</td>
                            <td class="p-3 text-cyan-300 font-bold">${t.seat_code}</td>
                            <td class="p-3 text-gray-200">$${Number(t.price).toFixed(2)}</td>
                            <td class="p-3">${statusBadge}</td>
                            <td class="p-3 text-gray-400">${t.booked_by_user_id ? 'User #' + t.booked_by_user_id : '—'}</td>
                        </tr>
                    `;
                }).join("");
            }
        } catch (e) {
            console.error(e);
        }
    },

    loadAuditLogs: async function() {
        const tbody = document.getElementById("table-audit-body");
        if (!tbody) return;
        try {
            const res = await fetch("/api/audit-logs");
            const data = await res.json();
            tbody.innerHTML = data.logs.map(l => {
                let resBadge = l.result === "SUCCESS"
                    ? '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-600">SUCCESS</span>'
                    : '<span class="px-2 py-0.5 rounded text-[10px] bg-rose-950 text-rose-300 border border-rose-600">FAILURE</span>';
                return `
                    <tr class="border-b border-gray-800 hover:bg-gray-800/40 font-mono text-xs">
                        <td class="p-3 text-gray-400">#${l.audit_id}</td>
                        <td class="p-3 text-gray-300">${l.timestamp}</td>
                        <td class="p-3 text-cyan-300 font-semibold">${l.action}</td>
                        <td class="p-3">${resBadge}</td>
                        <td class="p-3 text-gray-400">${l.user_id ? 'User #' + l.user_id : 'System'}</td>
                        <td class="p-3 text-gray-300 max-w-xs truncate" title="${l.payload_summary}">${l.payload_summary}</td>
                    </tr>
                `;
            }).join("");
        } catch (e) {
            console.error(e);
        }
    },

    loadConflictLogs: async function() {
        const tbody = document.getElementById("table-conflicts-body");
        if (!tbody) return;
        try {
            const res = await fetch("/api/conflicts");
            const data = await res.json();
            tbody.innerHTML = data.conflicts.map(c => {
                let sevBadge = "bg-gray-800 text-gray-300";
                if (c.severity === "CRITICAL") sevBadge = "bg-rose-950 text-rose-300 border-rose-600";
                else if (c.severity === "HIGH") sevBadge = "bg-amber-950 text-amber-300 border-amber-600";
                else if (c.severity === "MEDIUM") sevBadge = "bg-purple-950 text-purple-300 border-purple-600";

                return `
                    <tr class="border-b border-gray-800 hover:bg-gray-800/40 font-mono text-xs">
                        <td class="p-3 text-gray-400">#${c.conflict_id}</td>
                        <td class="p-3 text-gray-300">${c.detected_at}</td>
                        <td class="p-3 text-cyan-300 font-semibold">${c.conflict_type}</td>
                        <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] border ${sevBadge}">${c.severity}</span></td>
                        <td class="p-3 text-emerald-400 font-medium">${c.resolution_status}</td>
                        <td class="p-3 text-gray-300 max-w-sm truncate" title="${JSON.stringify(c.details)}">
                            ${c.details.anomaly_explanation || c.details.message || JSON.stringify(c.details)}
                        </td>
                    </tr>
                `;
            }).join("");
        } catch (e) {
            console.error(e);
        }
    },

    loadRules: async function() {
        const container = document.getElementById("rules-container");
        if (!container) return;
        try {
            const res = await fetch("/api/monitoring-rules");
            const data = await res.json();
            container.innerHTML = data.rules.map(r => `
                <div class="glass-panel p-4 rounded-xl border border-gray-700">
                    <div class="flex items-center justify-between">
                        <div class="font-bold text-sm text-cyan-300">${r.rule_name}</div>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-600">ACTIVE</span>
                    </div>
                    <div class="text-xs text-gray-400 mt-1">Type: ${r.rule_type}</div>
                    <div class="mt-3 p-2.5 rounded bg-gray-900 font-mono text-[11px] text-gray-300">
                        ${JSON.stringify(r.parameters, null, 2)}
                    </div>
                </div>
            `).join("");
        } catch (e) {
            console.error(e);
        }
    },

    showToast: function(message, type = "info") {
        const toast = document.createElement("div");
        let borderClass = "border-cyan-500 bg-gray-900/90 text-cyan-200";
        if (type === "success") borderClass = "border-emerald-500 bg-gray-900/90 text-emerald-200";
        if (type === "error") borderClass = "border-rose-500 bg-gray-900/90 text-rose-200";

        toast.className = `fixed bottom-5 right-5 z-50 flex items-center gap-3 px-4 py-3 rounded-lg border shadow-2xl backdrop-blur font-mono text-xs transition-all duration-300 transform translate-y-10 opacity-0 ${borderClass}`;
        toast.innerHTML = `<span>${message}</span>`;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove("translate-y-10", "opacity-0");
        }, 10);

        setTimeout(() => {
            toast.classList.add("translate-y-10", "opacity-0");
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
};

document.addEventListener("DOMContentLoaded", () => DBGuardApp.init());
