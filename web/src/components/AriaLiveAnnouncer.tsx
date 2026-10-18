import React from 'react';
import { useUiStore } from '../store/uiStore';

export const AriaLiveAnnouncer: React.FC = () => {
  const { liveAnnouncement } = useUiStore();

  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
    >
      {liveAnnouncement}
    </div>
  );
};
