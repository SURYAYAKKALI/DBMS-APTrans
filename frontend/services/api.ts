import { TestProject, TestRun, AnomalyReport, BusinessRule } from '../types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export const api = {
  getHealth: () => fetch(`${API_BASE}/health`).then(r => r.json()),
  
  getProjects: (): Promise<TestProject[]> => 
    fetch(`${API_BASE}/projects`).then(r => r.json()),
  
  createProject: (data: Partial<TestProject>): Promise<TestProject> =>
    fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(r => r.json()),

  testConnection: (engine: string = 'sqlite') =>
    fetch(`${API_BASE}/connections/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engine_type: engine })
    }).then(r => r.json()),

  createRun: (payload: any) =>
    fetch(`${API_BASE}/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()),

  executeRun: (runId: string) =>
    fetch(`${API_BASE}/runs/${runId}/execute`, { method: 'POST' }).then(r => r.json()),

  getRunTransactions: (runId: string) =>
    fetch(`${API_BASE}/runs/${runId}/transactions`).then(r => r.json()),

  getRunDependencies: (runId: string) =>
    fetch(`${API_BASE}/runs/${runId}/dependencies`).then(r => r.json()),

  getRunAnomalies: (runId: string): Promise<AnomalyReport[]> =>
    fetch(`${API_BASE}/runs/${runId}/anomalies`).then(r => r.json()),

  getRunReport: (runId: string) =>
    fetch(`${API_BASE}/runs/${runId}/report`).then(r => r.json()),

  getRules: (): Promise<BusinessRule[]> =>
    fetch(`${API_BASE}/rules`).then(r => r.json()),

  getOverviewKpis: () =>
    fetch(`${API_BASE}/analytics/overview`).then(r => r.json()),

  getBenchmarkComparison: (workload: string, concurrency: number) =>
    fetch(`${API_BASE}/analytics/benchmark-comparison?workload=${workload}&concurrency=${concurrency}`).then(r => r.json()),

  runLastItemDemo: (mitigation: boolean, isolation: string) =>
    fetch(`${API_BASE}/demo/last-item/run?mitigation=${mitigation}&isolation_level=${encodeURIComponent(isolation)}`, { method: 'POST' }).then(r => r.json()),

  runWriteSkewDemo: (mitigation: boolean, isolation: string) =>
    fetch(`${API_BASE}/demo/write-skew/run?mitigation=${mitigation}&isolation_level=${encodeURIComponent(isolation)}`, { method: 'POST' }).then(r => r.json())
};
