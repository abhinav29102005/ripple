import { create } from 'zustand';
import type { GraphNode, TenantId, ViewTab } from '../api/types';

interface UiState {
  tenant: TenantId;
  retractionId: string;
  selectedNode: GraphNode | null;
  hoveredNode: GraphNode | null;
  activeTab: ViewTab;
  viewMode: '3d' | '2d';
  sessionId: string | null;
  activeRankingId: string | null;
  isNoticeModalOpen: boolean;
  rippleTrigger: number;
  liveAnnouncement: string;

  setTenant: (tenant: TenantId) => void;
  setRetractionId: (id: string) => void;
  setSelectedNode: (node: GraphNode | null) => void;
  setHoveredNode: (node: GraphNode | null) => void;
  setActiveTab: (tab: ViewTab) => void;
  setViewMode: (mode: '3d' | '2d') => void;
  setSessionId: (id: string | null) => void;
  setActiveRankingId: (id: string | null) => void;
  setIsNoticeModalOpen: (open: boolean) => void;
  triggerRipple: () => void;
  announce: (message: string) => void;
}

function loadPersistedState(): { tenant?: TenantId; viewMode?: '3d' | '2d'; activeTab?: ViewTab } {
  try {
    const raw = localStorage.getItem('ripple_ui_prefs');
    if (raw) {
      return JSON.parse(raw);
    }
  } catch {
    // localStorage restricted or parsing failed
  }
  return {};
}

function savePersistedState(state: { tenant: TenantId; viewMode: '3d' | '2d'; activeTab: ViewTab }) {
  try {
    localStorage.setItem('ripple_ui_prefs', JSON.stringify(state));
  } catch {
    // localStorage restricted
  }
}

const initialPrefs = loadPersistedState();

export const useUiStore = create<UiState>((set, get) => ({
  tenant: initialPrefs.tenant || 'tenant_cardio',
  retractionId: 'SYN-RET-001',
  selectedNode: null,
  hoveredNode: null,
  activeTab: initialPrefs.activeTab || 'coordination',
  viewMode: initialPrefs.viewMode || '3d',
  sessionId: null,
  activeRankingId: null,
  isNoticeModalOpen: false,
  rippleTrigger: Date.now(),
  liveAnnouncement: '',

  setTenant: (tenant) => {
    set({ tenant, selectedNode: null });
    savePersistedState({
      tenant,
      viewMode: get().viewMode,
      activeTab: get().activeTab,
    });
  },

  setRetractionId: (retractionId) => {
    set({ retractionId, selectedNode: null, rippleTrigger: Date.now() });
  },

  setSelectedNode: (selectedNode) => set({ selectedNode }),

  setHoveredNode: (hoveredNode) => set({ hoveredNode }),

  setActiveTab: (activeTab) => {
    set({ activeTab });
    savePersistedState({
      tenant: get().tenant,
      viewMode: get().viewMode,
      activeTab,
    });
  },

  setViewMode: (viewMode) => {
    set({ viewMode });
    savePersistedState({
      tenant: get().tenant,
      viewMode,
      activeTab: get().activeTab,
    });
  },

  setSessionId: (sessionId) => set({ sessionId }),

  setActiveRankingId: (activeRankingId) => set({ activeRankingId }),

  setIsNoticeModalOpen: (isNoticeModalOpen) => set({ isNoticeModalOpen }),

  triggerRipple: () => set({ rippleTrigger: Date.now() }),

  announce: (liveAnnouncement) => set({ liveAnnouncement }),
}));
