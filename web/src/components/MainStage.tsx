import React, { Suspense, lazy, useState, useEffect } from 'react';
import { useUiStore } from '../store/uiStore';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { BlastView2D } from './scene/BlastView2D';
import { RotateCcw, Waves, Box, Layers, ListFilter } from 'lucide-react';

const BlastScene3D = lazy(() =>
  import('./scene/BlastScene3D').then((m) => ({ default: m.BlastScene3D }))
);

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
  } catch {
    return false;
  }
}

export const MainStage: React.FC = () => {
  const { retractionId, viewMode, setViewMode, triggerRipple } = useUiStore();
  const [hasWebGL, setHasWebGL] = useState(true);
  const [showAccessibleList, setShowAccessibleList] = useState(false);

  useEffect(() => {
    const webglSupported = detectWebGL();
    setHasWebGL(webglSupported);
    if (!webglSupported && viewMode === '3d') {
      setViewMode('2d');
    }
  }, [viewMode, setViewMode]);

  const { data: blastData, isLoading, error } = useQuery({
    queryKey: ['blastRadius', retractionId],
    queryFn: () => api.getBlastRadius(retractionId),
    refetchInterval: 5000,
  });

  const nodes = blastData?.nodes || [];
  const edges = blastData?.edges || [];

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-bg relative overflow-hidden">
      {/* Top Controls Bar */}
      <div className="h-9 px-3 border-b border-border bg-surface/80 backdrop-blur-sm flex items-center justify-between z-10 select-none">
        {/* View Controls */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => triggerRipple()}
            className="px-2 py-1 rounded bg-raised hover:bg-border text-xs text-text border border-border flex items-center gap-1 transition-colors"
            title="Replay expanding ripple wavefront across hop shells"
          >
            <Waves className="w-3.5 h-3.5 text-accent" />
            <span>Replay Ripple</span>
          </button>

          <button
            onClick={() => {
              const resetBtn = document.getElementById('btn-reset-camera');
              if (resetBtn) resetBtn.click();
            }}
            className="px-2 py-1 rounded bg-raised hover:bg-border text-xs text-secondary hover:text-text border border-border flex items-center gap-1 transition-colors"
            title="Reset 3D camera to default overview perspective"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset View</span>
          </button>

          {/* Hidden button for camera reset integration */}
          <button id="btn-reset-camera" className="hidden" aria-hidden="true" />
        </div>

        {/* Legend */}
        <div className="hidden lg:flex items-center gap-3 text-[11px] font-mono text-secondary">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rotate-45 bg-retraction-red rounded-sm" />
            <span>Retraction</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-at-risk-amber" />
            <span>Trial</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-accent rounded-sm" />
            <span>Review</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-[#6366f1]" />
            <span>Guideline</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#d946ef]" />
            <span>Decision</span>
          </span>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowAccessibleList(!showAccessibleList)}
            className={`p-1 rounded text-xs border ${
              showAccessibleList ? 'bg-raised text-accent border-accent' : 'bg-surface text-secondary border-border'
            }`}
            title="Toggle accessible entities list drawer"
            aria-label="Toggle accessible entity list"
          >
            <ListFilter className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setViewMode(viewMode === '3d' ? '2d' : '3d')}
            disabled={!hasWebGL}
            className={`px-2 py-1 rounded text-xs font-mono font-medium border flex items-center gap-1 transition-colors ${
              viewMode === '3d'
                ? 'bg-raised text-accent border-border hover:border-accent'
                : 'bg-raised text-secondary border-border hover:text-text'
            } ${!hasWebGL ? 'opacity-40 cursor-not-allowed' : ''}`}
            title={hasWebGL ? 'Toggle between 3D radial ripple scene and 2D overview' : 'WebGL not detected on device'}
          >
            {viewMode === '3d' ? <Box className="w-3 h-3 text-accent" /> : <Layers className="w-3 h-3" />}
            <span>{viewMode.toUpperCase()}</span>
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 relative overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">
            Loading evidence graph...
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-xs text-retraction-red">
            Failed to load blast radius data.
          </div>
        )}

        {!isLoading && !error && (
          <>
            {viewMode === '3d' && hasWebGL ? (
              <Suspense
                fallback={
                  <div className="w-full h-full flex items-center justify-center text-xs text-muted">
                    Initializing 3D ripple scene...
                  </div>
                }
              >
                <BlastScene3D nodes={nodes} edges={edges} />
              </Suspense>
            ) : (
              <BlastView2D nodes={nodes} edges={edges} />
            )}
          </>
        )}

        {/* Accessible Entities List Drawer */}
        {showAccessibleList && (
          <div className="absolute right-0 top-0 bottom-0 w-80 bg-surface/95 border-l border-border p-3 overflow-y-auto z-20 shadow-xl backdrop-blur-md">
            <div className="flex items-center justify-between pb-2 border-b border-border mb-2">
              <span className="text-xs font-semibold text-text">Keyboard Navigable Entities</span>
              <button
                onClick={() => setShowAccessibleList(false)}
                className="text-secondary hover:text-text text-xs"
              >
                ✕
              </button>
            </div>
            <div className="space-y-1">
              {nodes.map((n) => (
                <button
                  key={n.id}
                  onClick={() => useUiStore.getState().setSelectedNode(n)}
                  className="w-full text-left p-1.5 rounded hover:bg-raised border border-transparent hover:border-border text-xs flex items-center justify-between"
                >
                  <span className="font-mono text-secondary truncate">{n.id}</span>
                  <span className="text-[10px] text-muted">{n.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
