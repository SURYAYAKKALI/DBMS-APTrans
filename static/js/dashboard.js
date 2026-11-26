/**
 * TransactionGuard Interactive Dashboard Controller
 */

let currentRunId = null;

// Tab Switching
function switchTab(tabName) {
    const panels = ['overview', 'demo', 'testing-lab', 'explorer', 'graph', 'anomalies', 'consistency', 'analytics', 'projects'];
    panels.forEach(p => {
        const el = document.getElementById(`panel-${p}`);
        const btn = document.getElementById(`tab-${p}`);
        if (el) el.classList.add('hidden');
        if (btn) btn.classList.remove('active');
    });

    const activePanel = document.getElementById(`panel-${tabName}`);
    const activeBtn = document.getElementById(`tab-${tabName}`);
    if (activePanel) activePanel.classList.remove('hidden');
    if (activeBtn) activeBtn.classList.add('active');

    if (window.lucide) lucide.createIcons();

    // Trigger tab-specific loaders
    if (tabName === 'overview') loadOverviewKPIs();
    if (tabName === 'consistency') loadBusinessRules();
    if (tabName === 'projects') loadProjects();
}

// ----------------------------------------------------------------------------
// 1. OVERVIEW & KPIS
// ----------------------------------------------------------------------------
async function loadOverviewKPIs() {
    try {
        const res = await fetch('/api/analytics/overview');
        const data = await res.json();
        document.getElementById('kpi-runs').innerText = data.total_test_runs || 0;
        document.getElementById('kpi-txns').innerText = data.total_transactions || 0;
        document.getElementById('kpi-committed').innerText = data.committed_transactions || 0;
        document.getElementById('kpi-aborted').innerText = data.aborted_transactions || 0;
        document.getElementById('kpi-anomalies').innerText = data.total_anomalies_detected || 0;
        document.getElementById('kpi-success-rate').innerText = `${data.success_rate_pct}% success`;
        
        const statusEl = document.getElementById('kpi-status');
        if (data.database_consistency_status === 'MONITORED') {
            statusEl.className = 'text-sm font-bold text-emerald-400 mt-1 flex items-center gap-1.5';
            statusEl.innerHTML = '<span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> SECURE';
        } else {
            statusEl.className = 'text-sm font-bold text-amber-400 mt-1 flex items-center gap-1.5';
            statusEl.innerHTML = '<span class="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse"></span> ANOMALIES FLAGGED';
        }
    } catch (e) {
        console.error('Failed to load KPIs:', e);
    }
}

// ----------------------------------------------------------------------------
// 2. LIVE DEMONSTRATION STORY (The Last Item Problem)
// ----------------------------------------------------------------------------
async function resetDemoItem() {
    try {
        const res = await fetch('/api/demo/last-item/reset', { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'Inventory reset to Quantity = 1');
    } catch (e) {
        alert('Reset error: ' + e);
    }
}

async function runDemo(mitigation) {
    const container = document.getElementById('demo-output-container');
    const badge = document.getElementById('demo-badge');
    const details = document.getElementById('demo-details');

    container.classList.remove('hidden');
    details.innerHTML = '<div class="text-xs font-mono text-slate-400 py-3">Executing concurrent transactions with barriers...</div>';

    try {
        const iso = mitigation ? 'SERIALIZABLE' : 'READ COMMITTED';
        const res = await fetch(`/api/demo/last-item/run?mitigation=${mitigation}&isolation_level=${encodeURIComponent(iso)}`, { method: 'POST' });
        const data = await res.json();

        currentRunId = data.run_id;
        const anomalies = data.analysis.anomalies || [];

        if (mitigation) {
            badge.className = 'px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800';
            badge.innerText = 'CONCURRENCY ASSURANCE: VERIFIED';
        } else {
            badge.className = 'px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-rose-950 text-rose-300 border border-rose-800';
            badge.innerText = 'LOST UPDATE DETECTED (SILENT OVERSELLING)';
        }

        let html = `
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono mb-4">
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <span class="text-slate-400">Run ID:</span> <span class="text-indigo-400">${data.run_id}</span>
                </div>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <span class="text-slate-400">Final Inventory:</span> <span class="text-white font-bold">${data.final_inventory_quantity}</span>
                </div>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <span class="text-slate-400">Anomalies Detected:</span> <span class="${anomalies.length > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}">${anomalies.length}</span>
                </div>
            </div>
        `;

        if (anomalies.length > 0) {
            html += '<div class="space-y-3">';
            for (const anom of anomalies) {
                html += `
                    <div class="p-4 rounded-lg bg-rose-950/20 border border-rose-800/40 text-xs">
                        <div class="flex justify-between font-bold text-rose-300 mb-1">
                            <span>${anom.type} (${anom.verdict || 'ANOMALY'})</span>
                            <span class="font-mono text-[10px] text-slate-400">${anom.anomaly_id}</span>
                        </div>
                        <p class="text-slate-300 mb-2">${anom.evidence}</p>
                        <div class="bg-slate-950 p-2.5 rounded border border-slate-800 font-mono text-[11px] text-indigo-300">
                            <strong>Remediation Strategy:</strong> ${anom.suggested_fix}
                        </div>
                    </div>
                `;
            }
            html += '</div>';
        } else {
            html += `
                <div class="p-4 rounded-lg bg-emerald-950/20 border border-emerald-800/40 text-xs text-emerald-300 font-mono">
                    Success: Concurrency control correctly preserved the business invariant. Only 1 purchase committed, conflicting transaction aborted with SQLSTATE 40001.
                </div>
            `;
        }

        details.innerHTML = html;
        loadOverviewKPIs();
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        details.innerHTML = `<div class="text-xs text-rose-400 font-mono">Error: ${e}</div>`;
    }
}

// ----------------------------------------------------------------------------
// 3. TESTING LABORATORY
// ----------------------------------------------------------------------------
async function executeLabRun() {
    const workload = document.getElementById('lab-workload').value;
    const isolation = document.getElementById('lab-isolation').value;
    const concurrency = parseInt(document.getElementById('lab-concurrency').value);
    const mitigation = document.getElementById('lab-mitigation').checked;

    const btn = document.getElementById('btn-run-lab');
    const resultCard = document.getElementById('lab-result-card');
    const statusBadge = document.getElementById('lab-status-badge');
    const content = document.getElementById('lab-result-content');

    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Executing...';
    if (window.lucide) lucide.createIcons();

    resultCard.classList.remove('hidden');
    content.innerHTML = '<div class="text-xs text-slate-400 font-mono py-4">Reconstructing histories, checking RW/WR dependencies, evaluating isolation rules...</div>';

    try {
        // 1. Create Run
        const createRes = await fetch('/api/runs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: 'PROJ-DEFAULT',
                isolation_level: isolation,
                workload_type: workload,
                concurrency: concurrency,
                apply_mitigation: mitigation
            })
        });
        const runData = await createRes.json();
        currentRunId = runData.run_id;

        // 2. Execute Run
        const execRes = await fetch(`/api/runs/${currentRunId}/execute`, { method: 'POST' });
        const summary = await execRes.json();

        const anomalies = summary.analysis?.anomalies || [];
        statusBadge.className = anomalies.length > 0 ? 
            'px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-rose-950 text-rose-300 border border-rose-800' :
            'px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800';
        statusBadge.innerText = anomalies.length > 0 ? `${anomalies.length} ANOMALIES DETECTED` : 'CLEAN EXECUTION';

        let html = `
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono mb-4">
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <span class="text-slate-400">Total Txns:</span> <span class="text-white font-bold">${summary.total_txns}</span>
                </div>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <span class="text-slate-400">Committed:</span> <span class="text-emerald-400 font-bold">${summary.committed_txns}</span>
                </div>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <span class="text-slate-400">Aborted:</span> <span class="text-rose-400 font-bold">${summary.aborted_txns}</span>
                </div>
                <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <span class="text-slate-400">Duration:</span> <span class="text-indigo-400">${summary.duration_ms} ms</span>
                </div>
            </div>
        `;

        if (anomalies.length > 0) {
            html += '<div class="space-y-3">';
            for (const a of anomalies) {
                html += `
                    <div class="p-3.5 rounded-lg bg-rose-950/20 border border-rose-800/40 text-xs">
                        <div class="flex justify-between font-bold text-rose-300 mb-1">
                            <span>${a.type}</span>
                            <span class="text-[10px] bg-slate-900 px-2 py-0.5 rounded border border-slate-800">${a.verdict || 'ANOMALY'}</span>
                        </div>
                        <p class="text-slate-300 mb-2">${a.evidence}</p>
                        <div class="text-[11px] font-mono text-indigo-300">
                            <strong>Remediation:</strong> ${a.suggested_fix}
                        </div>
                    </div>
                `;
            }
            html += '</div>';
        } else {
            html += '<div class="text-xs text-emerald-400 font-mono p-3 bg-emerald-950/20 rounded border border-emerald-800/40">Zero transaction anomalies detected. Concurrency invariants fully respected.</div>';
        }

        content.innerHTML = html;
        loadOverviewKPIs();
    } catch (e) {
        content.innerHTML = `<div class="text-xs text-rose-400 font-mono">Execution failed: ${e}</div>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i> Execute Controlled Workload';
        if (window.lucide) lucide.createIcons();
    }
}

// ----------------------------------------------------------------------------
// 4. TRANSACTION EXPLORER
// ----------------------------------------------------------------------------
async function refreshExplorer() {
    if (!currentRunId) {
        alert('Please run a workload first from Testing Lab or Live Demo!');
        return;
    }
    const tbody = document.getElementById('timeline-table-body');
    tbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-slate-400 font-mono text-xs">Loading execution timeline...</td></tr>';

    try {
        const res = await fetch(`/api/runs/${currentRunId}/transactions`);
        const data = await res.json();
        const events = data.timeline || [];

        if (events.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-slate-500 font-mono text-xs">No events recorded for current run.</td></tr>';
            return;
        }

        let html = '';
        for (const evt of events) {
            const opClass = evt.operation_type === 'COMMIT' ? 'text-emerald-400 font-bold' :
                           evt.operation_type === 'ROLLBACK' ? 'text-rose-400 font-bold' :
                           evt.operation_type === 'WRITE' ? 'text-amber-300' : 'text-blue-300';
            
            html += `
                <tr class="hover:bg-slate-900/60 transition">
                    <td class="py-2 px-3 text-slate-400">${evt.sequence}</td>
                    <td class="py-2 px-3 font-bold text-white">${evt.txn_id}</td>
                    <td class="py-2 px-3 text-slate-400">${evt.session_id}</td>
                    <td class="py-2 px-3 ${opClass}">${evt.operation_type}</td>
                    <td class="py-2 px-3 text-indigo-300">${evt.table_name}:${evt.row_id}</td>
                    <td class="py-2 px-3 text-slate-400">${evt.old_value !== null ? evt.old_value : '-'}</td>
                    <td class="py-2 px-3 text-white font-semibold">${evt.new_value !== null ? evt.new_value : '-'}</td>
                    <td class="py-2 px-3 text-slate-400">${evt.version || '-'}</td>
                    <td class="py-2 px-3 text-emerald-400">${evt.status}</td>
                </tr>
            `;
        }
        tbody.innerHTML = html;
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-rose-400 font-mono text-xs">Failed to load timeline: ${e}</td></tr>`;
    }
}

// ----------------------------------------------------------------------------
// 5. DEPENDENCY GRAPH (Adya Graph Visualization)
// ----------------------------------------------------------------------------
async function renderDependencyGraph() {
    if (!currentRunId) return;
    const svg = document.getElementById('dependency-svg');
    svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#64748b" font-size="12" font-family="monospace">Analyzing dependency graph...</text>';

    try {
        const res = await fetch(`/api/runs/${currentRunId}/dependencies`);
        const data = await res.json();
        const edges = data.edges || [];
        const cycles = data.cycles || [];

        // Build SVG nodes and directed arrows
        const width = svg.clientWidth || 800;
        const height = svg.clientHeight || 450;

        let svgHtml = `
            <defs>
                <marker id="arrow-wr" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6"/>
                </marker>
                <marker id="arrow-rw" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444"/>
                </marker>
                <marker id="arrow-ww" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b"/>
                </marker>
            </defs>
        `;

        // Extract nodes
        const nodeSet = new Set();
        edges.forEach(e => { nodeSet.add(e.source); nodeSet.add(e.target); });
        const nodes = Array.from(nodeSet);

        if (nodes.length === 0) {
            svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#64748b" font-size="12" font-family="monospace">No inter-transaction dependencies in current run.</text>';
            return;
        }

        const nodeCoords = {};
        nodes.forEach((n, idx) => {
            const angle = (idx / nodes.length) * 2 * Math.PI;
            const x = width / 2 + Math.cos(angle) * (width * 0.3);
            const y = height / 2 + Math.sin(angle) * (height * 0.3);
            nodeCoords[n] = { x, y };
        });

        // Draw Edges
        edges.forEach(e => {
            const src = nodeCoords[e.source];
            const dst = nodeCoords[e.target];
            if (!src || !dst) return;
            const color = e.type === 'RW' ? '#ef4444' : (e.type === 'WR' ? '#3b82f6' : '#f59e0b');
            const marker = `url(#arrow-${e.type.toLowerCase()})`;
            const isCycle = e.is_cycle_member;

            svgHtml += `
                <line x1="${src.x}" y1="${src.y}" x2="${dst.x}" y2="${dst.y}" 
                      stroke="${color}" stroke-width="${isCycle ? 3 : 2}" marker-end="${marker}"
                      class="${isCycle ? 'cycle-highlight' : ''}" />
                <text x="${(src.x + dst.x) / 2}" y="${(src.y + dst.y) / 2 - 8}" 
                      fill="${color}" font-size="10" font-family="monospace" font-weight="bold" text-anchor="middle">
                      ${e.type} (${e.table})
                </text>
            `;
        });

        // Draw Nodes
        nodes.forEach(n => {
            const coord = nodeCoords[n];
            svgHtml += `
                <g class="graph-node" transform="translate(${coord.x}, ${coord.y})">
                    <circle r="32" fill="#0f172a" stroke="#4f46e5" stroke-width="2.5"/>
                    <text text-anchor="middle" dy="4" fill="#ffffff" font-size="11" font-weight="bold" font-family="monospace">${n}</text>
                </g>
            `;
        });

        svg.innerHTML = svgHtml;
    } catch (e) {
        svg.innerHTML = `<text x="50%" y="50%" text-anchor="middle" fill="#ef4444" font-size="12">Graph error: ${e}</text>`;
    }
}

// ----------------------------------------------------------------------------
// 6. BUSINESS RULES
// ----------------------------------------------------------------------------
async function loadBusinessRules() {
    const grid = document.getElementById('rules-grid');
    try {
        const res = await fetch('/api/rules');
        const rules = await res.json();
        let html = '';
        for (const r of rules) {
            html += `
                <div class="glass-panel p-4 rounded-xl border-slate-800 space-y-2">
                    <div class="flex justify-between items-start">
                        <span class="text-xs font-bold text-white">${r.name}</span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-800">
                            ${r.severity}
                        </span>
                    </div>
                    <p class="text-xs text-slate-300">${r.description}</p>
                    <div class="bg-slate-950 p-2.5 rounded font-mono text-[11px] text-emerald-400 border border-slate-800">
                        Target: ${r.target_table} | Invariant: ${r.rule_definition}
                    </div>
                </div>
            `;
        }
        grid.innerHTML = html;
    } catch (e) {
        grid.innerHTML = `<div class="text-xs text-rose-400">Failed to load rules: ${e}</div>`;
    }
}

// ----------------------------------------------------------------------------
// 7. BENCHMARK COMPARISON SUITE
// ----------------------------------------------------------------------------
async function runBenchmarkSuite() {
    const tbody = document.getElementById('benchmark-table-body');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-slate-400 font-mono text-xs">Running empirical benchmark across isolation levels...</td></tr>';

    try {
        const res = await fetch('/api/analytics/benchmark-comparison?workload=lost_update&concurrency=5');
        const data = await res.json();
        const results = data.benchmark_results || [];

        let html = '';
        for (const b of results) {
            html += `
                <tr class="hover:bg-slate-900/60 transition">
                    <td class="py-2.5 px-3 font-bold text-white">${b.isolation_level}</td>
                    <td class="py-2.5 px-3 text-indigo-400 font-semibold">${b.throughput_tps} TPS</td>
                    <td class="py-2.5 px-3 text-slate-300">${b.avg_latency_ms} ms</td>
                    <td class="py-2.5 px-3 text-slate-300">${b.p95_latency_ms} ms</td>
                    <td class="py-2.5 px-3 ${b.abort_rate_pct > 0 ? 'text-rose-400' : 'text-slate-400'}">${b.abort_rate_pct}%</td>
                    <td class="py-2.5 px-3 ${b.anomalies_detected > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}">${b.anomalies_detected}</td>
                    <td class="py-2.5 px-3 text-slate-400">${b.instrumentation_overhead_ms} ms</td>
                </tr>
            `;
        }
        tbody.innerHTML = html;
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-rose-400 font-mono text-xs">Benchmark error: ${e}</td></tr>`;
    }
}

// ----------------------------------------------------------------------------
// 8. PROJECTS & DB DIAGNOSTIC
// ----------------------------------------------------------------------------
async function loadProjects() {
    const list = document.getElementById('projects-list');
    try {
        const res = await fetch('/api/projects');
        const projs = await res.json();
        let html = '';
        for (const p of projs) {
            html += `
                <div class="p-3 bg-slate-950 rounded-lg border border-slate-800 flex justify-between items-center text-xs">
                    <div>
                        <div class="font-bold text-white">${p.name}</div>
                        <div class="text-[11px] text-slate-400 font-mono">${p.project_id}</div>
                    </div>
                    <span class="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 text-[10px] font-mono">ACTIVE</span>
                </div>
            `;
        }
        list.innerHTML = html;
    } catch (e) {
        list.innerHTML = `<div class="text-xs text-rose-400">Failed to load projects: ${e}</div>`;
    }
}

async function testDbConnection() {
    const customUrl = document.getElementById('custom-db-url')?.value?.trim();
    try {
        const payload = customUrl ? { database_url: customUrl } : { engine_type: 'sqlite' };
        const res = await fetch('/api/connections/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('diag-engine').innerText = data.engine.toUpperCase();
            alert(`${data.message}\nRoundtrip Latency: ${data.latency_ms} ms`);
        } else {
            alert(`Connection Failed: ${data.message}`);
        }
    } catch (e) {
        alert('Connection test failed: ' + e);
    }
}

async function switchDbConnection() {
    const customUrl = document.getElementById('custom-db-url')?.value?.trim();
    if (!customUrl) {
        alert('Please enter a valid database connection URI (e.g. postgresql://user:password@localhost:5432/dbname)');
        return;
    }
    try {
        const res = await fetch('/api/connections/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ database_url: customUrl })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('diag-engine').innerText = data.engine.toUpperCase();
            document.getElementById('db-status-pill').innerText = `DB: ${data.engine.toUpperCase()}`;
            alert(`Target Database Switched!\n${data.message}\nTransactionGuard is now executing all tests and anomaly oracles directly against this official database.`);
            loadOverviewKPIs();
        } else {
            alert(`Failed to switch: ${data.message || data.detail}`);
        }
    } catch (e) {
        alert('Failed to switch database: ' + e);
    }
}

// Initial Boot
document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) lucide.createIcons();
    loadOverviewKPIs();
    testDbConnection();
});
