import React from 'react';
import { useUiStore } from '../store/uiStore';
import { X, AlertTriangle, ShieldCheck, User, Users, FileText, CheckCircle2 } from 'lucide-react';

export const Inspector: React.FC = () => {
  const { selectedNode, setSelectedNode } = useUiStore();

  if (!selectedNode) {
    return (
      <div className="h-44 border-b border-border bg-surface p-4 flex flex-col justify-center items-center text-center select-none">
        <FileText className="w-6 h-6 text-muted mb-2 opacity-50" />
        <span className="text-xs text-secondary font-medium">No Node Selected</span>
        <span className="text-[11px] text-muted max-w-[240px] mt-0.5">
          Click any node in the blast radius to inspect clinical dependencies and responsible owners.
        </span>
      </div>
    );
  }

  const isAtRisk = selectedNode.status === 'at_risk';

  return (
    <div data-testid="inspector-card" tabIndex={0} role="region" aria-label="Selected Node Inspector" className="h-44 border-b border-border bg-surface p-3 flex flex-col justify-between overflow-y-auto focus-visible:ring-1 focus-visible:ring-accent">
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-raised border border-border text-secondary">
              {selectedNode.label}
            </span>
            <span className="font-mono text-xs font-semibold text-text truncate max-w-[180px]">
              {selectedNode.id}
            </span>
          </div>
          <button
            onClick={() => setSelectedNode(null)}
            className="text-secondary hover:text-text p-0.5 rounded hover:bg-raised"
            aria-label="Deselect node"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {selectedNode.title && (
          <p className="text-xs font-medium text-text leading-snug line-clamp-2 mb-2">
            {selectedNode.title}
          </p>
        )}

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          {selectedNode.status && (
            <div className="flex items-center gap-1">
              <span className="text-muted">Status:</span>
              <span
                data-testid="inspector-status"
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  isAtRisk
                    ? 'bg-at-risk-amber/15 text-at-risk-amber border border-at-risk-amber/30'
                    : 'bg-ok-green/15 text-ok-green border border-ok-green/30'
                }`}
              >
                {isAtRisk ? <AlertTriangle className="w-3 h-3" /> : <ShieldCheck className="w-3 h-3" />}
                <span>{selectedNode.status}</span>
              </span>
            </div>
          )}

          {selectedNode.committee && (
            <div className="flex items-center gap-1 truncate" title={selectedNode.committee}>
              <Users className="w-3 h-3 text-muted flex-shrink-0" />
              <span className="truncate text-secondary">{selectedNode.committee}</span>
            </div>
          )}
        </div>

        {selectedNode.notify && selectedNode.notify.length > 0 && (
          <div className="mt-2 pt-2 border-t border-border">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider block mb-1">
              Owners to Notify ({selectedNode.notify.length}):
            </span>
            <div className="flex flex-wrap gap-1">
              {selectedNode.notify.map((owner, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-raised border border-border text-secondary"
                >
                  <User className="w-2.5 h-2.5 text-muted" />
                  <span>{owner}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {selectedNode.yi !== undefined && (
          <div className="mt-1 flex items-center gap-3 text-[11px] font-mono text-muted">
            <span>yi: <strong className="text-text tabular-nums">{selectedNode.yi.toFixed(4)}</strong></span>
            {selectedNode.sei !== undefined && (
              <span>sei: <strong className="text-text tabular-nums">{selectedNode.sei.toFixed(4)}</strong></span>
            )}
          </div>
        )}
      </div>

      <div className="text-[10px] text-muted font-mono flex items-center gap-1 mt-1">
        <CheckCircle2 className="w-3 h-3 text-accent" />
        <span>FalkorDB Verified Graph Node</span>
      </div>
    </div>
  );
};
