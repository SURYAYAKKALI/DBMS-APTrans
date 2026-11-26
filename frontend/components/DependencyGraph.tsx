'use client';

import React from 'react';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import 'reactflow/dist/style.css';

interface Props {
  nodes: any[];
  edges: any[];
  onNodeClick?: (nodeId: string) => void;
}

export default function DependencyGraph({ nodes, edges, onNodeClick }: Props) {
  return (
    <div className="w-full h-[550px] bg-slate-950 rounded-xl border border-slate-800 relative">
      <div className="absolute top-3 left-4 z-10 flex gap-3 text-xs bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-700">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span> WR (Write-Read)</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-500"></span> RW (Anti-Dependency)</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span> WW (Write-Write)</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full ring-2 ring-red-400 bg-transparent animate-pulse"></span> Cycle Member</span>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_, node) => onNodeClick?.(node.id)}
      >
        <Background color="#334155" gap={16} />
        <Controls />
        <MiniMap nodeStrokeWidth={3} className="bg-slate-900 border border-slate-800" />
      </ReactFlow>
    </div>
  );
}
