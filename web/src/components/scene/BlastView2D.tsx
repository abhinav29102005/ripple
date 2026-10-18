import React, { useMemo } from 'react';
import { useUiStore } from '../../store/uiStore';
import type { GraphNode, GraphEdge } from '../../api/types';
import { AlertTriangle, Users, BookOpen, FileCheck, FileCode, HelpCircle } from 'lucide-react';

interface BlastView2DProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const BlastView2D: React.FC<BlastView2DProps> = ({ nodes }) => {
  const { selectedNode, setSelectedNode, hoveredNode, setHoveredNode } = useUiStore();

  // Group nodes by hop distance / logical category
  const shells = useMemo(() => {
    const s0: GraphNode[] = [];
    const s1: GraphNode[] = [];
    const s2: GraphNode[] = [];
    const s3: GraphNode[] = [];
    const s4: GraphNode[] = [];
    const s5: GraphNode[] = [];

    nodes.forEach((n) => {
      switch (n.label) {
        case 'Retraction':
          s0.push(n);
          break;
        case 'Trial':
          s1.push(n);
          break;
        case 'Review':
          s2.push(n);
          break;
        case 'Guideline':
          s3.push(n);
          break;
        case 'Decision':
          s4.push(n);
          break;
        case 'Committee':
        case 'Person':
          s5.push(n);
          break;
        default:
          s2.push(n);
      }
    });

    return [
      { name: 'Retraction (Epicenter)', nodes: s0 },
      { name: 'Retracted Trials (Hop 1)', nodes: s1 },
      { name: 'Contaminated Reviews (Hop 2)', nodes: s2 },
      { name: 'Impacted Guidelines (Hop 3)', nodes: s3 },
      { name: 'Hospital Decisions (Hop 4)', nodes: s4 },
      { name: 'Committees & Owners (Hop 5)', nodes: s5 },
    ].filter((s) => s.nodes.length > 0);
  }, [nodes]);

  const getNodeIcon = (label: string, status?: string) => {
    if (label === 'Decision' && status === 'at_risk') return <AlertTriangle className="w-3.5 h-3.5 text-at-risk-amber" />;
    switch (label) {
      case 'Retraction': return <AlertTriangle className="w-3.5 h-3.5 text-retraction-red" />;
      case 'Trial': return <FileCode className="w-3.5 h-3.5 text-at-risk-amber" />;
      case 'Review': return <BookOpen className="w-3.5 h-3.5 text-accent" />;
      case 'Guideline': return <FileCheck className="w-3.5 h-3.5 text-[#6366f1]" />;
      case 'Decision': return <AlertTriangle className="w-3.5 h-3.5 text-secondary" />;
      case 'Committee':
      case 'Person': return <Users className="w-3.5 h-3.5 text-muted" />;
      default: return <HelpCircle className="w-3.5 h-3.5 text-muted" />;
    }
  };

  return (
    <div className="w-full h-full p-6 overflow-y-auto bg-bg select-none" role="region" aria-label="2D Blast Radius Evidence Cascade">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
              Evidence Cascade (Hierarchical 2D Overview)
            </h2>
            <p className="text-[11px] text-muted">
              Nodes arranged in outward ripple shells by hop distance from retraction notice.
            </p>
          </div>
          <span className="text-xs font-mono text-secondary px-2 py-0.5 rounded bg-raised border border-border">
            {nodes.length} Nodes in Radius
          </span>
        </div>

        <div className="space-y-4">
          {shells.map((shell, idx) => (
            <div key={idx} className="p-3 rounded border border-border bg-surface">
              <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-border/50">
                <span className="text-xs font-mono font-medium text-secondary flex items-center gap-2">
                  <span className="w-4 h-4 rounded-full bg-raised border border-border flex items-center justify-center text-[10px] text-muted">
                    {idx}
                  </span>
                  <span>{shell.name}</span>
                </span>
                <span className="text-[10px] font-mono text-muted">{shell.nodes.length} entities</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {shell.nodes.map((node) => {
                  const isSelected = selectedNode?.id === node.id;
                  const isHovered = hoveredNode?.id === node.id;
                  const isAtRisk = node.status === 'at_risk';

                  return (
                    <button
                      key={node.id}
                      onClick={() => setSelectedNode(node)}
                      onMouseEnter={() => setHoveredNode(node)}
                      onMouseLeave={() => setHoveredNode(null)}
                      className={`text-left p-2.5 rounded border text-xs transition-colors flex items-start gap-2 focus-visible:ring-1 focus-visible:ring-accent ${
                        isSelected
                          ? 'bg-raised border-accent text-text'
                          : isHovered
                          ? 'bg-raised border-muted/80 text-text'
                          : 'bg-bg border-border text-secondary hover:text-text'
                      }`}
                    >
                      <div className="mt-0.5 flex-shrink-0">
                        {getNodeIcon(node.label, node.status)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-mono text-[11px] font-semibold truncate">
                            {node.id}
                          </span>
                          {isAtRisk && (
                            <span className="px-1 py-0.2 rounded text-[9px] font-mono bg-at-risk-amber/15 text-at-risk-amber border border-at-risk-amber/30">
                              at_risk
                            </span>
                          )}
                        </div>
                        {node.title && (
                          <p className="text-[11px] text-muted truncate mt-0.5">
                            {node.title}
                          </p>
                        )}
                        {node.committee && (
                          <p className="text-[10px] text-muted/70 truncate mt-0.5">
                            {node.committee}
                          </p>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
