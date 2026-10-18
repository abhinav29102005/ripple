import React, { useState } from 'react';
import { useUiStore } from '../store/uiStore';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { ShieldCheck, ArrowDown, ArrowUp, ChevronDown, ChevronRight, XCircle, ArrowUpCircle, AlertCircle } from 'lucide-react';
import type { Alert } from '../api/types';

export const RankedAlerts: React.FC = () => {
  const { tenant, retractionId, setActiveRankingId, announce } = useUiStore();
  const queryClient = useQueryClient();
  const [expandedAlerts, setExpandedAlerts] = useState<Record<string, boolean>>({});

  const { data: rankingsData, isLoading, error } = useQuery({
    queryKey: ['rankings', tenant, retractionId],
    queryFn: async () => {
      const data = await api.getRankings(tenant, retractionId);
      if (data.ranking_id) {
        setActiveRankingId(data.ranking_id);
      }
      return data;
    },
    refetchInterval: 3000,
  });

  const dismissMutation = useMutation({
    mutationFn: async (alert: Alert) => {
      return api.recordEpisode(tenant, {
        session_id: null,
        kind: 'dismiss',
        reason: alert.reason_category,
        weight_bucket: alert.weight_bucket,
        flips: alert.flips,
        ext_review: alert.review_id,
        ext_retraction: retractionId,
        notes: `User dismissed alert ${alert.review_id}`,
      });
    },
    onSuccess: (res, alert) => {
      announce(`Dismissed alert ${alert.review_id}. Episodic memory updated.`);
      if (res.consolidation?.created_rules?.length) {
        announce(`Librarian consolidated new rule: ${res.consolidation.created_rules.join(', ')}`);
      }
      queryClient.invalidateQueries({ queryKey: ['rankings'] });
      queryClient.invalidateQueries({ queryKey: ['memory'] });
    },
  });

  const escalateMutation = useMutation({
    mutationFn: async (alert: Alert) => {
      return api.recordEpisode(tenant, {
        session_id: null,
        kind: 'escalate',
        reason: alert.reason_category,
        weight_bucket: alert.weight_bucket,
        flips: alert.flips,
        ext_review: alert.review_id,
        ext_retraction: retractionId,
        notes: `User escalated alert ${alert.review_id}`,
      });
    },
    onSuccess: (_, alert) => {
      announce(`Escalated alert ${alert.review_id}. Episodic memory updated.`);
      queryClient.invalidateQueries({ queryKey: ['rankings'] });
      queryClient.invalidateQueries({ queryKey: ['memory'] });
    },
  });

  const toggleWhy = (reviewId: string) => {
    setExpandedAlerts((prev) => ({
      ...prev,
      [reviewId]: !prev[reviewId],
    }));
  };

  const alerts = rankingsData?.ranked_alerts || [];
  const rankingId = rankingsData?.ranking_id || '';

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-surface">
      <div className="p-3 border-b border-border bg-raised flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-secondary">
            Ranked Alerts
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-bg text-secondary border border-border">
            {alerts.length}
          </span>
        </div>
        <span className="text-[10px] font-mono text-muted">
          Ranking: {rankingId ? rankingId.slice(-8) : 'active'}
        </span>
      </div>

      <div tabIndex={0} role="region" aria-label="Ranked Alerts List" className="flex-1 overflow-y-auto p-2 space-y-2 focus-visible:ring-1 focus-visible:ring-accent">
        {isLoading && (
          <div className="p-6 text-center text-xs text-muted">Loading ranked alerts...</div>
        )}

        {error && (
          <div className="p-3 rounded bg-retraction-red/10 border border-retraction-red/30 text-retraction-red text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>Failed to load alert rankings for {tenant}.</span>
          </div>
        )}

        {!isLoading && !error && alerts.length === 0 && (
          <div className="p-8 text-center text-xs text-muted">
            No affected reviews identified for retraction {retractionId}.
          </div>
        )}

        {alerts.map((alert) => {
          const isExpanded = !!expandedAlerts[alert.review_id];
          const hasScoreDrop = alert.delta < 0;
          const hasScoreBoost = alert.delta > 0;

          return (
            <div
              key={alert.review_id}
              data-testid={`alert-card-${alert.review_id}`}
              className="p-3 rounded border border-border bg-raised hover:border-muted/60 transition-colors"
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-accent">#{alert.rank}</span>
                  <span className="text-xs font-mono font-semibold text-text">{alert.review_id}</span>
                  <span
                    data-testid="alert-reason-category"
                    className="text-[10px] px-1.5 py-0.2 rounded bg-bg text-secondary border border-border"
                  >
                    {alert.reason_category}
                  </span>
                </div>

                {alert.safety_floor_active && (
                  <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-ok-green/15 text-ok-green border border-ok-green/30" title="Safety floor enforces score >= 0.5 for fabrication and clinical flips">
                    <ShieldCheck className="w-3 h-3" />
                    <span>Floor Active</span>
                  </span>
                )}
              </div>

              <p className="text-xs text-secondary line-clamp-1 mb-2 font-medium">
                {alert.title}
              </p>

              {/* Numerical Metrics Bar */}
              <div className="grid grid-cols-4 gap-1 p-1.5 rounded bg-bg border border-border text-[11px] font-mono tabular-nums mb-2">
                <div>
                  <span className="text-[10px] text-muted block">Base</span>
                  <span className="text-secondary font-medium">{alert.base.toFixed(4)}</span>
                </div>
                <div>
                  <span className="text-[10px] text-muted block">Score</span>
                  <span className={`font-semibold flex items-center gap-0.5 ${hasScoreDrop ? 'text-ok-green' : hasScoreBoost ? 'text-at-risk-amber' : 'text-text'}`}>
                    {hasScoreDrop && <ArrowDown className="w-2.5 h-2.5" />}
                    {hasScoreBoost && <ArrowUp className="w-2.5 h-2.5" />}
                    <span data-testid="alert-score-value">{alert.score.toFixed(4)}</span>
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-muted block">Weight</span>
                  <span className="text-secondary">{(alert.weight_share * 100).toFixed(1)}%</span>
                </div>
                <div>
                  <span className="text-[10px] text-muted block">Flips</span>
                  <span className={alert.flips ? 'text-at-risk-amber font-semibold' : 'text-muted'}>
                    {alert.flips ? 'true' : 'false'}
                  </span>
                </div>
              </div>

              {/* Actions & Why this rank */}
              <div className="flex items-center justify-between text-xs pt-1 border-t border-border/50">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => dismissMutation.mutate(alert)}
                    disabled={dismissMutation.isPending}
                    className="px-2 py-0.5 rounded bg-bg hover:bg-border text-[11px] text-secondary hover:text-text border border-border flex items-center gap-1 transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-3 h-3 text-muted" />
                    <span>Dismiss</span>
                  </button>
                  <button
                    onClick={() => escalateMutation.mutate(alert)}
                    disabled={escalateMutation.isPending}
                    className="px-2 py-0.5 rounded bg-bg hover:bg-border text-[11px] text-secondary hover:text-text border border-border flex items-center gap-1 transition-colors disabled:opacity-50"
                  >
                    <ArrowUpCircle className="w-3 h-3 text-accent" />
                    <span>Escalate</span>
                  </button>
                </div>

                <button
                  onClick={() => toggleWhy(alert.review_id)}
                  className="text-[11px] text-accent hover:underline flex items-center gap-0.5 font-medium"
                >
                  {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  <span>Why this rank?</span>
                </button>
              </div>

              {/* Expandable Explanation Details */}
              {isExpanded && (
                <AlertExplanationDetails
                  tenant={tenant}
                  rankingId={rankingId}
                  alert={alert}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const AlertExplanationDetails: React.FC<{
  tenant: string;
  rankingId: string;
  alert: Alert;
}> = ({ tenant, rankingId, alert }) => {
  const { data: explainData, isLoading } = useQuery({
    queryKey: ['explain', tenant, rankingId, alert.review_id],
    queryFn: () => api.getExplain(tenant, rankingId, alert.review_id),
    enabled: !!rankingId,
  });

  const cat = (alert.reason_category || 'unknown').toLowerCase();
  const reasonW = cat === 'fabrication' ? 1.0 : cat === 'error' ? 0.6 : cat === 'administrative' ? 0.2 : 0.5;
  const ws = alert.weight_share || 0.0;
  const f = alert.flips ? 1.0 : 0.0;
  const glCount = (alert.guidelines || []).length;
  const glVal = Math.min(glCount / 3.0, 1.0);

  const appliedRules = explainData?.rules_applied || [];

  return (
    <div className="mt-2.5 p-2.5 rounded bg-bg border border-border text-[11px] font-mono space-y-2">
      {isLoading ? (
        <div className="text-muted text-[10px]">Loading graph explainability path...</div>
      ) : appliedRules.length === 0 ? (
        <div>
          <span className="text-secondary font-semibold block">No learned rules applied. Base score only</span>
        </div>
      ) : (
        <div>
          <span className="text-secondary font-semibold block mb-1">
            Rules Applied ({appliedRules.length}):
          </span>
          <div className="space-y-1">
            {appliedRules.map((rule) => (
              <div key={rule.rule_id} className="p-1.5 rounded bg-raised border border-border text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-accent">{rule.rule_id}</span>
                  <span className={`font-semibold ${rule.delta < 0 ? 'text-ok-green' : 'text-at-risk-amber'}`}>
                    {rule.delta > 0 ? `+${rule.delta}` : rule.delta}
                  </span>
                </div>
                <div className="text-secondary mt-0.5">{rule.description}</div>
                {rule.learned_from_episodes && rule.learned_from_episodes.length > 0 && (
                  <div className="text-muted text-[9px] mt-0.5">
                    Source episodes: {rule.learned_from_episodes.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Formula Breakdown */}
      <div className="pt-2 border-t border-border text-[10px] text-muted leading-relaxed">
        <span className="font-semibold text-secondary block mb-0.5">Formula Breakdown:</span>
        <div>base = 0.4 × reason_w ({cat} → {reasonW}) + 0.3 × weight_share ({(ws * 100).toFixed(1)}%) + 0.2 × flips ({f.toFixed(1)}) + 0.1 × (guidelines/3: {glCount}/3)</div>
        <div className="text-text font-semibold mt-0.5">
          = {(0.4 * reasonW).toFixed(4)} + {(0.3 * ws).toFixed(4)} + {(0.2 * f).toFixed(4)} + {(0.1 * glVal).toFixed(4)} = {alert.base.toFixed(4)}
        </div>
        {alert.safety_floor_active && (
          <div className="text-ok-green font-medium mt-1">
            Clinical safety floor (&gt;= 0.5000) active: Critical alert cannot be dropped by procedural rules.
          </div>
        )}
      </div>
    </div>
  );
};
