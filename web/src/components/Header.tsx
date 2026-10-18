import React, { useState } from 'react';
import { useUiStore } from '../store/uiStore';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { Activity, Plus, Zap, ShieldAlert, Cpu } from 'lucide-react';
import type { TenantId } from '../api/types';

export const Header: React.FC = () => {
  const {
    tenant,
    setTenant,
    retractionId,
    setRetractionId,
    setIsNoticeModalOpen,
    announce,
  } = useUiStore();

  const queryClient = useQueryClient();
  const [isLoadingDemo, setIsLoadingDemo] = useState(false);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 5000,
  });

  const handleLoadDemo = async () => {
    setIsLoadingDemo(true);
    try {
      const res = await api.loadDemoScenario(tenant, retractionId);
      announce(`Loaded demo scenario for ${tenant}: ${res.ranked_alerts_count} alerts available.`);
      queryClient.invalidateQueries({ queryKey: ['rankings'] });
      queryClient.invalidateQueries({ queryKey: ['memory'] });
      queryClient.invalidateQueries({ queryKey: ['blastRadius'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    } catch (err) {
      console.error('Failed to load demo scenario:', err);
    } finally {
      setIsLoadingDemo(false);
    }
  };

  const modeLabel = health?.llm_mode === 'on' ? 'Autonomous (Groq)' : 'Fixed Planner';

  return (
    <header className="h-12 border-b border-border bg-surface px-4 flex items-center justify-between flex-shrink-0 select-none">
      <div className="flex items-center gap-4">
        {/* Brand */}
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm tracking-wider text-text font-mono">RIPPLE</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-raised border border-border text-muted">v2.1</span>
        </div>

        {/* Separator */}
        <div className="h-4 w-px bg-border" />

        {/* Tenant Selector */}
        <div className="flex items-center gap-1.5">
          <label htmlFor="tenant-select" className="text-xs text-muted font-medium">Team:</label>
          <select
            id="tenant-select"
            value={tenant}
            onChange={(e) => setTenant(e.target.value as TenantId)}
            className="bg-raised border border-border rounded px-2 py-1 text-xs text-text font-medium hover:border-muted focus-visible:ring-1 focus-visible:ring-accent"
          >
            <option value="tenant_cardio">Cardiology Evidence Board</option>
            <option value="tenant_onco">Oncology Formulary Board</option>
          </select>
        </div>

        {/* Retraction Selector */}
        <div className="flex items-center gap-1.5">
          <label htmlFor="retraction-select" className="text-xs text-muted font-medium">Notice:</label>
          <select
            id="retraction-select"
            value={retractionId}
            onChange={(e) => setRetractionId(e.target.value)}
            className="bg-raised border border-border rounded px-2 py-1 text-xs font-mono text-text hover:border-muted focus-visible:ring-1 focus-visible:ring-accent"
          >
            <option value="SYN-RET-001">SYN-RET-001 (Fabrication)</option>
            <option value="SYN-RET-002">SYN-RET-002 (Error)</option>
            <option value="SYN-RET-003">SYN-RET-003 (Administrative)</option>
          </select>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsNoticeModalOpen(true)}
            className="px-2.5 py-1 rounded bg-raised hover:bg-border text-xs text-text border border-border flex items-center gap-1 transition-colors"
            title="Submit a retraction notice into the coordinator"
          >
            <Plus className="w-3.5 h-3.5 text-accent" />
            <span>Submit Notice</span>
          </button>

          <button
            onClick={handleLoadDemo}
            disabled={isLoadingDemo}
            className="px-2.5 py-1 rounded bg-raised hover:bg-border text-xs text-text border border-border flex items-center gap-1 transition-colors disabled:opacity-50"
            title="Inject low-weight administrative alerts to train tenant memory"
          >
            <Zap className="w-3.5 h-3.5 text-at-risk-amber" />
            <span>{isLoadingDemo ? 'Loading...' : 'Load Demo'}</span>
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Analyst Mode Badge */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-raised border border-border text-[11px] font-mono text-secondary">
          <Cpu className="w-3 h-3 text-accent" />
          <span>Analyst: {modeLabel}</span>
        </div>

        {/* Health status */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-raised border border-border text-[11px] font-mono text-secondary" title="FalkorDB local connection status">
          <Activity className="w-3 h-3 text-ok-green" />
          <span>FalkorDB</span>
        </div>

        {/* Synthetic Data Badge */}
        <div className="px-2 py-0.5 rounded bg-raised/80 border border-border text-[10px] font-mono text-muted uppercase tracking-wider">
          Synthetic Data
        </div>

        {/* Medical Disclaimer */}
        <div className="flex items-center gap-1 text-[11px] text-muted max-w-[280px] truncate" title="Decision-support for human review; does not recommend changing clinical practice.">
          <ShieldAlert className="w-3.5 h-3.5 text-secondary flex-shrink-0" />
          <span className="truncate">Decision-support only</span>
        </div>
      </div>
    </header>
  );
};
