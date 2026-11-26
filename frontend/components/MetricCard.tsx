import React from 'react';

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  badge?: string;
  badgeColor?: 'green' | 'red' | 'blue' | 'yellow';
}

export default function MetricCard({ title, value, subtitle, badge, badgeColor = 'blue' }: Props) {
  const badgeStyles = {
    green: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    red: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
    blue: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
    yellow: 'bg-amber-500/20 text-amber-300 border-amber-500/30'
  }[badgeColor];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</span>
        {badge && (
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${badgeStyles}`}>
            {badge}
          </span>
        )}
      </div>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      {subtitle && <div className="text-xs text-slate-400">{subtitle}</div>}
    </div>
  );
}
