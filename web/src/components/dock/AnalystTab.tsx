import React, { useState } from 'react';
import { useUiStore } from '../../store/uiStore';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';
import { Play, Cpu, CheckCircle2, Ticket, Network, FileText, AlertCircle } from 'lucide-react';
import type { AnalystResponse } from '../../api/types';

export const AnalystTab: React.FC = () => {
  const { tenant, retractionId, announce } = useUiStore();
  const [query, setQuery] = useState('What should we do first?');
  const [analystResult, setAnalystResult] = useState<AnalystResponse | null>(null);

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
  });

  const analystMutation = useMutation({
    mutationFn: () => api.runAnalyst({ tenant, retraction_id: retractionId, prompt: query }),
    onSuccess: (data) => {
      setAnalystResult(data);
      announce(`Analyst generated remediation plan. Target decision: ${data.target_decision_id || 'none'}. Ticket: ${data.ticket_created || 'none'}.`);
    },
  });

  const modeLabel = health?.llm_mode === 'on' ? 'Autonomous (Groq)' : 'Fixed Planner';

  return (
    <div className="h-full flex flex-col p-3 overflow-hidden bg-surface select-none">
      {/* Input bar */}
      <div className="flex items-center gap-2 mb-3 flex-shrink-0">
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-raised border border-border text-xs text-secondary flex-shrink-0 font-mono">
          <Cpu className="w-3.5 h-3.5 text-accent" />
          <span>Mode: {modeLabel}</span>
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask Analyst (e.g. 'What should we do first?', 'Who knows about Cardiology?')..."
          className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-xs text-text focus-visible:ring-1 focus-visible:ring-accent"
        />

        <button
          onClick={() => analystMutation.mutate()}
          disabled={analystMutation.isPending}
          className="px-3 py-1.5 rounded bg-accent text-bg hover:opacity-90 font-medium text-xs flex items-center gap-1.5 disabled:opacity-50 transition-opacity flex-shrink-0"
        >
          <Play className="w-3.5 h-3.5 fill-current" />
          <span>{analystMutation.isPending ? 'Executing...' : 'Run Plan'}</span>
        </button>
      </div>

      {/* Main output area */}
      <div className="flex-1 grid grid-cols-2 gap-3 min-h-0">
        {/* Left: Execution Trace */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <Network className="w-3.5 h-3.5 text-accent" />
              <span>MCP Graph Tool Execution Trace</span>
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-bg text-secondary border border-border">
              {analystResult?.tool_trace?.length || 0} Tools
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {!analystResult && !analystMutation.isPending && (
              <div className="text-center text-[11px] text-muted py-8">
                Click 'Run Plan' to trigger autonomous MCP tool selection and FalkorDB graph algorithms.
              </div>
            )}

            {analystMutation.isPending && (
              <div className="text-center text-xs text-muted py-8 animate-pulse">
                Analyst is inspecting knowledge graph & dispatching tools...
              </div>
            )}

            {analystMutation.error && (
              <div className="p-3 rounded bg-retraction-red/10 border border-retraction-red/30 text-retraction-red text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>Analyst execution failed: {(analystMutation.error as Error).message}</span>
              </div>
            )}

            {analystResult?.tool_trace?.map((step, idx) => (
              <div key={idx} className="p-2 rounded bg-surface border border-border text-[11px] font-mono">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-accent font-semibold flex items-center gap-1">
                    <span className="text-muted">#{idx + 1}</span>
                    <span>{step.tool}</span>
                  </span>
                  {step.algorithm && (
                    <span className="px-1.5 py-0.2 rounded text-[9px] bg-raised border border-border text-at-risk-amber">
                      {step.algorithm}
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-muted truncate mb-1">
                  args: {JSON.stringify(step.args || {})}
                </div>
                {step.output && (
                  <div className="text-[10px] text-secondary bg-raised p-1.5 rounded border border-border/50 break-words leading-tight">
                    {typeof step.output === 'string' ? step.output : JSON.stringify(step.output)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Recommendation & Ticket */}
        <div className="flex flex-col rounded border border-border bg-bg overflow-hidden">
          <div className="px-2.5 py-1.5 border-b border-border bg-raised flex items-center justify-between text-xs">
            <span className="font-semibold text-secondary flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-ok-green" />
              <span>Remediation Recommendation & Audit</span>
            </span>
            {analystResult?.ticket_created && (
              <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.2 rounded bg-ok-green/15 text-ok-green border border-ok-green/30">
                <Ticket className="w-3 h-3" />
                <span>{analystResult.ticket_created}</span>
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3 text-xs leading-relaxed">
            {!analystResult && (
              <div className="text-center text-[11px] text-muted py-8">
                Structured clinical remediation guidance will appear here.
              </div>
            )}

            {analystResult && (
              <div className="space-y-3">
                {analystResult.target_decision_id && (
                  <div className="p-2.5 rounded bg-raised border border-border flex items-center justify-between font-mono text-[11px]">
                    <span className="text-muted">Target Compromised Decision:</span>
                    <span className="text-at-risk-amber font-bold">{analystResult.target_decision_id}</span>
                  </div>
                )}

                <div className="text-secondary whitespace-pre-wrap font-sans text-xs leading-normal">
                  {analystResult.recommendation}
                </div>

                <div className="pt-2 border-t border-border flex items-center justify-between text-[10px] font-mono text-muted">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-accent" />
                    <span>FalkorDB Logged ToolCall Audit Node</span>
                  </span>
                  <span>Algorithms: {analystResult.algorithms_used.join(', ') || 'none'}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
