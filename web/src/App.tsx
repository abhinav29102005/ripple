import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Header } from './components/Header';
import { MainStage } from './components/MainStage';
import { Inspector } from './components/Inspector';
import { RankedAlerts } from './components/RankedAlerts';
import { BottomDock } from './components/dock/BottomDock';
import { NoticeModal } from './components/NoticeModal';
import { AriaLiveAnnouncer } from './components/AriaLiveAnnouncer';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AriaLiveAnnouncer />
      <NoticeModal />

      <div className="w-screen h-screen flex flex-col bg-bg text-text overflow-hidden">
        {/* Top Header */}
        <Header />

        {/* Center Workspace (Stage + Inspector/Alerts) */}
        <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
          {/* Main Stage (60% width) */}
          <div className="flex-[3] flex flex-col min-w-0 border-r border-border">
            <MainStage />
          </div>

          {/* Right Column: Inspector + Alerts (40% width) */}
          <div className="flex-[2] flex flex-col min-w-[340px] max-w-[520px] bg-surface overflow-hidden">
            <Inspector />
            <RankedAlerts />
          </div>
        </div>

        {/* Bottom Dock */}
        <BottomDock />
      </div>
    </QueryClientProvider>
  );
};

export default App;
