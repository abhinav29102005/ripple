import React from 'react';
import { useUiStore } from '../../store/uiStore';
import { CoordinationTab } from './CoordinationTab';
import { MemoryTab } from './MemoryTab';
import { AnalystTab } from './AnalystTab';
import { ChatTab } from './ChatTab';
import { ProofTab } from './ProofTab';
import { Layers, Brain, Cpu, MessageSquare, ShieldCheck } from 'lucide-react';
import type { ViewTab } from '../../api/types';

export const BottomDock: React.FC = () => {
  const { activeTab, setActiveTab } = useUiStore();

  const tabs: { id: ViewTab; label: string; icon: React.ReactNode }[] = [
    { id: 'coordination', label: 'Coordination Board', icon: <Layers className="w-3.5 h-3.5" /> },
    { id: 'memory', label: 'Adaptive Memory', icon: <Brain className="w-3.5 h-3.5" /> },
    { id: 'analyst', label: 'Autonomous Analyst', icon: <Cpu className="w-3.5 h-3.5" /> },
    { id: 'chat', label: 'Team Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> },
    { id: 'proof', label: 'Empirical Proof', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="h-64 border-t border-border bg-surface flex flex-col flex-shrink-0">
      {/* Tab Header Bar */}
      <div className="h-9 border-b border-border bg-raised px-3 flex items-center justify-between select-none">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 rounded-t text-xs font-medium flex items-center gap-1.5 transition-colors border-b-2 ${
                  isActive
                    ? 'border-accent text-text bg-surface'
                    : 'border-transparent text-secondary hover:text-text hover:bg-surface/50'
                }`}
              >
                <span className={isActive ? 'text-accent' : 'text-muted'}>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Body */}
      <div className="flex-1 min-h-0">
        {activeTab === 'coordination' && <CoordinationTab />}
        {activeTab === 'memory' && <MemoryTab />}
        {activeTab === 'analyst' && <AnalystTab />}
        {activeTab === 'chat' && <ChatTab />}
        {activeTab === 'proof' && <ProofTab />}
      </div>
    </div>
  );
};
