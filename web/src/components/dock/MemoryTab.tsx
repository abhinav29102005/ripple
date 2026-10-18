import React from 'react';
import { useUiStore } from '../../store/uiStore';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { Brain, History, BookOpen } from 'lucide-react';

export const MemoryTab: React.FC = () => {
  const { tenant } = useUiStore();

  const { data: memData, isLoading } = useQuery({
    queryKey: ['memory', tenant],
    queryFn: () => api.getMemory(tenant),
    refetchInterval: 3000,
  });

  const rules = memData?.active_rules || [];
  const facts = memData?.facts || [];
  const episodes = memData?.episodes || [];

  return (
    <div className="h-full flex flex-col p-3 overflow-hidden bg-surface select-none">
      <div className="grid grid-cols-3 gap-3 flex-1 min-h-0">
        {/* Procedural Rules */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5 text-accent" />
              <span>Learned Procedural Rules</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-secondary border border-border">
              {rules.length}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {isLoading && <div className="text-xs text-muted text-center py-6">Loading memory...</div>}
            {!isLoading && rules.length === 0 && (
              <div className="text-center text-[11px] text-muted py-6">
                No active rules consolidated yet. Dismiss or escalate alerts to train the Librarian.
              </div>
            )}
            {rules.map((rule) => (
              <div key={rule.id} className="p-2.5 rounded bg-surface border border-border text-xs">
                <div className="flex items-center justify-between font-mono mb-1">
                  <span className="font-bold text-accent">{rule.id}</span>
                  <span className={`font-semibold ${rule.delta < 0 ? 'text-ok-green' : 'text-at-risk-amber'}`}>
                    {rule.delta > 0 ? `+${rule.delta}` : rule.delta}
                  </span>
                </div>
                <p className="text-[11px] text-secondary leading-snug mb-2">{rule.description}</p>
                <div className="flex items-center justify-between text-[10px] font-mono text-muted pt-1 border-t border-border/50">
                  <span>Support: {rule.support} eps</span>
                  <span>Hit Rate: {(rule.hit_rate * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Semantic Facts */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-at-risk-amber" />
              <span>Semantic Memory & Facts</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-secondary border border-border">
              {facts.length}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {facts.length === 0 && (
              <div className="text-center text-[11px] text-muted py-6">No facts recorded</div>
            )}
            {facts.map((fact) => (
              <div key={fact.id} className="p-2.5 rounded bg-surface border border-border text-xs">
                <div className="flex items-center justify-between font-mono mb-1">
                  <span className="text-text font-semibold truncate max-w-[150px]">{fact.key}</span>
                  <span className="text-[10px] text-muted">fact_{fact.id.slice(-6)}</span>
                </div>
                <div className="text-secondary text-[11px] font-medium bg-raised p-1.5 rounded border border-border font-mono break-all">
                  {fact.value}
                </div>
                {fact.supersedes_id && (
                  <span className="text-[10px] font-mono text-muted block mt-1">
                    Supersedes: {fact.supersedes_id}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Feedback Episodes */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <History className="w-3.5 h-3.5 text-muted" />
              <span>Feedback Episodes</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-secondary border border-border">
              {episodes.length}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {episodes.length === 0 && (
              <div className="text-center text-[11px] text-muted py-6">No episodic feedback recorded yet</div>
            )}
            {episodes.map((ep) => (
              <div key={ep.id} className="p-2 rounded bg-surface border border-border text-[11px] font-mono">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-text font-semibold">{ep.ext_review || ep.id}</span>
                  <span
                    className={`px-1.5 py-0.2 rounded text-[10px] font-medium ${
                      ep.kind === 'dismiss'
                        ? 'bg-retraction-red/15 text-retraction-red border border-retraction-red/30'
                        : 'bg-accent/15 text-accent border border-accent/30'
                    }`}
                  >
                    {ep.kind}
                  </span>
                </div>
                <div className="text-[10px] text-muted flex items-center justify-between">
                  <span>reason: {ep.reason}</span>
                  <span>weight: {ep.weight_bucket}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
