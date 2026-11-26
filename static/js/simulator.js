/**
 * DBGuard Simulator Engine & Dual-Timeline Visualizer
 * Renders Thread 1 vs Thread 2 execution traces side by side.
 */

window.DBSimulator = {
    renderTimeline: function(timeline, containerId = "timeline-container") {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (!timeline || timeline.length === 0) {
            container.innerHTML = `
                <div class="col-span-2 text-center py-12 text-gray-400">
                    <i data-lucide="play-circle" class="w-12 h-12 mx-auto mb-3 opacity-40 text-cyan-400"></i>
                    <p class="text-sm font-medium">Select a concurrency scenario above and click "Run Simulation" to observe dual-thread execution.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        // Split into Thread 1 steps and Thread 2 steps
        const t1Steps = timeline.filter(s => s.thread.includes("T1"));
        const t2Steps = timeline.filter(s => s.thread.includes("T2"));

        let t1Html = t1Steps.map((s, idx) => this._renderStepCard(s, idx, "cyan")).join("");
        let t2Html = t2Steps.map((s, idx) => this._renderStepCard(s, idx, "purple")).join("");

        container.innerHTML = `
            <!-- Thread 1 Column -->
            <div class="space-y-4">
                <div class="flex items-center justify-between pb-2 border-b border-gray-700">
                    <div class="flex items-center gap-2">
                        <span class="w-3 h-3 rounded-full bg-cyan-400 animate-pulse"></span>
                        <h4 class="font-semibold text-cyan-300 text-sm tracking-wider uppercase">Thread 1 (Connection T1)</h4>
                    </div>
                    <span class="text-xs font-mono text-gray-400">${t1Steps.length} Steps</span>
                </div>
                <div class="space-y-3">
                    ${t1Html || '<p class="text-xs text-gray-500 italic">No operations recorded for T1.</p>'}
                </div>
            </div>

            <!-- Thread 2 Column -->
            <div class="space-y-4">
                <div class="flex items-center justify-between pb-2 border-b border-gray-700">
                    <div class="flex items-center gap-2">
                        <span class="w-3 h-3 rounded-full bg-purple-400 animate-pulse"></span>
                        <h4 class="font-semibold text-purple-300 text-sm tracking-wider uppercase">Thread 2 (Connection T2)</h4>
                    </div>
                    <span class="text-xs font-mono text-gray-400">${t2Steps.length} Steps</span>
                </div>
                <div class="space-y-3">
                    ${t2Html || '<p class="text-xs text-gray-500 italic">No operations recorded for T2.</p>'}
                </div>
            </div>
        `;

        if (window.lucide) lucide.createIcons();
    },

    _renderStepCard: function(step, idx, color) {
        let badgeClass = "bg-gray-800 text-gray-300 border-gray-600";
        let iconName = "check-circle";

        if (step.status === "LOCK_WAIT") {
            badgeClass = "bg-amber-950/80 text-amber-300 border-amber-600 badge-lock-wait";
            iconName = "lock";
        } else if (step.status === "DEADLOCK" || step.status === "DEADLOCK_ABORTED" || step.status === "ERROR") {
            badgeClass = "bg-rose-950/80 text-rose-300 border-rose-600 badge-deadlock";
            iconName = "alert-triangle";
        } else if (step.status === "WARNING") {
            badgeClass = "bg-amber-900/60 text-amber-200 border-amber-500";
            iconName = "alert-circle";
        } else if (step.status === "COMMITTED") {
            badgeClass = "bg-emerald-950/80 text-emerald-300 border-emerald-600";
            iconName = "database";
        } else if (step.status === "ROLLED_BACK") {
            badgeClass = "bg-rose-900/60 text-rose-300 border-rose-500";
            iconName = "rotate-ccw";
        }

        return `
            <div class="timeline-step glass-panel p-3.5 rounded-lg border-l-4 ${color === 'cyan' ? 'border-l-cyan-500' : 'border-l-purple-500'}">
                <div class="flex items-center justify-between mb-1.5">
                    <span class="text-xs font-mono font-semibold px-2 py-0.5 rounded border ${badgeClass} flex items-center gap-1.5">
                        <i data-lucide="${iconName}" class="w-3.5 h-3.5"></i>
                        ${step.action}
                    </span>
                    <span class="text-[11px] font-mono text-gray-400">Step #${step.step_no}</span>
                </div>
                <div class="text-xs font-mono text-gray-200 mt-1 break-words">
                    ${step.value ? step.value : `<span class="text-gray-400">Target: ${step.resource}</span>`}
                </div>
                ${step.wait_ms > 0 ? `
                    <div class="mt-2 text-[10px] font-mono text-amber-400 flex items-center gap-1">
                        <i data-lucide="clock" class="w-3 h-3"></i>
                        <span>Lock wait duration: ${step.wait_ms} ms</span>
                    </div>
                ` : ''}
            </div>
        `;
    },

    renderComparison: function(result, containerId = "comparison-container") {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (!result || result.initial_balance === undefined) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <p class="text-sm">Run a scenario to inspect before-and-after serialized state comparisons.</p>
                </div>
            `;
            return;
        }

        const isCorrupted = result.anomaly_detected || result.data_loss > 0;
        const initial = Number(result.initial_balance || 1000).toFixed(2);
        const expected = Number(result.expected_final || 700).toFixed(2);
        const actual = Number(result.final_balance || 0).toFixed(2);
        const dataLoss = Number(result.data_loss || 0).toFixed(2);

        container.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div class="p-4 rounded-xl bg-gray-800/80 border border-gray-700">
                    <div class="text-xs font-medium text-gray-400 uppercase tracking-wider">Initial Balance</div>
                    <div class="text-2xl font-bold font-mono text-white mt-1">$${initial}</div>
                    <div class="text-[11px] text-gray-400 mt-1">Starting ledger record</div>
                </div>

                <div class="p-4 rounded-xl bg-gray-800/80 border border-gray-700">
                    <div class="text-xs font-medium text-gray-400 uppercase tracking-wider">T1 + T2 Deductions</div>
                    <div class="text-2xl font-bold font-mono text-cyan-400 mt-1">-$300.00</div>
                    <div class="text-[11px] text-gray-400 mt-1">T1: -$100, T2: -$200</div>
                </div>

                <div class="p-4 rounded-xl bg-gray-800/80 border border-gray-700">
                    <div class="text-xs font-medium text-gray-400 uppercase tracking-wider">Expected Balance</div>
                    <div class="text-2xl font-bold font-mono text-emerald-400 mt-1">$${expected}</div>
                    <div class="text-[11px] text-gray-400 mt-1">Mathematically correct ($1000 - $300)</div>
                </div>

                <div class="p-4 rounded-xl ${isCorrupted ? 'bg-rose-950/40 border-rose-600' : 'bg-emerald-950/40 border-emerald-600'} border">
                    <div class="text-xs font-medium ${isCorrupted ? 'text-rose-400' : 'text-emerald-400'} uppercase tracking-wider">
                        ${isCorrupted ? 'Actual Corrupted Balance' : 'Actual Serialized Balance'}
                    </div>
                    <div class="text-2xl font-bold font-mono ${isCorrupted ? 'text-rose-400' : 'text-emerald-400'} mt-1">$${actual}</div>
                    <div class="text-[11px] ${isCorrupted ? 'text-rose-300 font-semibold' : 'text-emerald-300'} mt-1">
                        ${isCorrupted ? `Data Loss Detected: $${dataLoss}` : 'Zero Data Loss (100% Consistent)'}
                    </div>
                </div>
            </div>

            <div class="mt-4 p-3.5 rounded-lg ${isCorrupted ? 'bg-rose-900/30 border border-rose-700/60 text-rose-200' : 'bg-emerald-900/30 border border-emerald-700/60 text-emerald-200'} text-xs font-mono leading-relaxed">
                <div class="font-bold mb-1 flex items-center gap-1.5">
                    <i data-lucide="${isCorrupted ? 'shield-alert' : 'shield-check'}" class="w-4 h-4"></i>
                    ${isCorrupted ? 'ANOMALY ANALYSIS' : 'PREVENTION MECHANISM CONFIRMED'}
                </div>
                ${result.message}
            </div>
        `;

        if (window.lucide) lucide.createIcons();
    }
};
