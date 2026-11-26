export type IsolationLevel = 'READ COMMITTED' | 'REPEATABLE READ' | 'SERIALIZABLE' | 'READ UNCOMMITTED';

export type WorkloadType = 
  | 'lost_update' 
  | 'write_skew' 
  | 'non_repeatable_read' 
  | 'dirty_read' 
  | 'read_skew' 
  | 'stress_concurrency';

export interface TestProject {
  project_id: string;
  name: string;
  description?: string;
  database_config: string;
  created_at?: string;
}

export interface TestRun {
  run_id: string;
  project_id: string;
  isolation_level: IsolationLevel;
  workload_type: WorkloadType;
  status: string;
  total_txns: number;
  committed_txns: number;
  aborted_txns: number;
  anomalies_detected: number;
  execution_duration_ms: number;
}

export interface OperationEvent {
  event_id: string;
  run_id: string;
  txn_id: string;
  session_id: string;
  sequence: number;
  operation_type: 'BEGIN' | 'READ' | 'WRITE' | 'COMMIT' | 'ROLLBACK';
  table_name: string;
  row_id: string;
  old_value?: string;
  new_value?: string;
  version?: number;
  timestamp: string;
  status: string;
}

export interface DependencyEdge {
  edge_id: string;
  source: string;
  target: string;
  type: 'WR' | 'RW' | 'WW';
  table: string;
  row_id: string;
  details: string;
  is_cycle_member?: boolean;
}

export interface AnomalyReport {
  anomaly_id: string;
  run_id: string;
  type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  involved_txns: string[];
  affected_records: string[];
  expected_behavior: string;
  observed_behavior: string;
  evidence: string;
  suggested_fix: string;
  verdict?: string;
  compliance_note?: string;
}

export interface BusinessRule {
  rule_id: string;
  name: string;
  description?: string;
  target_table: string;
  rule_definition: string;
  severity: string;
  enabled: boolean;
}
