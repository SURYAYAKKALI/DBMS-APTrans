import React from 'react';
import { AnomalyReport } from '../types';

interface Props {
  anomaly: AnomalyReport;
  onInvestigate?: () => void;
}

export default function AnomalyCard({ anomaly, onInvestigate }: Props) {
  const isCritical = anomaly.severity === 'CRITICAL';
  return (
    <div className={`p-5 rounded-xl border transition-all ${
      isCritical ? 'bg-red-950/20 border-red-800/60' : 'bg-amber-950/20 border-amber-800/60'
    }`}>
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-0.5 rounded text-xs font-semibold uppercase ${
            isCritical ? 'bg-red-500/20 text-red-300 border border-red-500/40' : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
          }`}>
            {anomaly.severity}
          </span>
          <span className="text-xs text-slate-400 font-mono">{anomaly.anomaly_id}</span>
        </div>
        <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
          {anomaly.verdict || 'ANOMALY'}
        </span>
      </div>

      <h3 className="text-base font-bold text-white mb-1.5">{anomaly.type}</h3>
      <p className="text-sm text-slate-300 mb-3">{anomaly.evidence}</p>

      <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800 mb-3 text-xs font-mono space-y-1">
        <div className="text-slate-400"><span className="text-indigo-400">Involved Txns:</span> {anomaly.involved_txns?.join(', ')}</div>
        <div className="text-slate-400"><span className="text-indigo-400">Affected Records:</span> {anomaly.affected_records?.join(', ')}</div>
      </div>

      <div className="text-xs bg-indigo-950/30 border border-indigo-800/50 p-2.5 rounded-lg text-indigo-200">
        <span className="font-semibold text-indigo-300 block mb-0.5">Remediation:</span>
        {anomaly.suggested_fix}
      </div>
    </div>
  );
}
