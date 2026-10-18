import React, { useState, useRef, useEffect } from 'react';
import { useUiStore } from '../store/uiStore';
import { api } from '../api/client';
import { useQueryClient } from '@tanstack/react-query';
import { X, Send, AlertTriangle } from 'lucide-react';

export const NoticeModal: React.FC = () => {
  const { isNoticeModalOpen, setIsNoticeModalOpen, announce } = useUiStore();
  const queryClient = useQueryClient();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [retractionId, setRetractionId] = useState('SYN-RET-004');
  const [trialId, setTrialId] = useState('SYN-TR-0004');
  const [reason, setReason] = useState('Data fabrication and falsification in clinical patient records');
  const [reasonCategory, setReasonCategory] = useState('fabrication');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isNoticeModalOpen) {
      if (!dialog.open) dialog.showModal();
    } else {
      if (dialog.open) dialog.close();
    }
  }, [isNoticeModalOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await api.submitRetraction({
        retraction_id: retractionId,
        trial_id: trialId,
        reason,
        reason_category: reasonCategory,
      });
      announce(`Retraction notice ${retractionId} submitted for ingestion.`);
      setIsNoticeModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['blastRadius'] });
      queryClient.invalidateQueries({ queryKey: ['rankings'] });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit retraction notice');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <dialog
      ref={dialogRef}
      onClose={() => setIsNoticeModalOpen(false)}
      className="bg-surface text-text border border-border rounded-panel p-0 max-w-lg w-full backdrop:bg-black/60 shadow-xl m-auto"
      aria-labelledby="modal-title"
    >
      <div className="p-4 border-b border-border flex items-center justify-between bg-raised">
        <h2 id="modal-title" className="text-sm font-semibold tracking-wide flex items-center gap-2">
          <span>Submit Retraction Notice</span>
          <span className="text-xs px-2 py-0.5 rounded bg-bg text-secondary border border-border">Coordination Ingest</span>
        </h2>
        <button
          onClick={() => setIsNoticeModalOpen(false)}
          className="text-secondary hover:text-text p-1 rounded hover:bg-border/50"
          aria-label="Close modal"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="p-4 space-y-3">
        {error && (
          <div className="p-2.5 rounded bg-retraction-red/10 border border-retraction-red/30 text-retraction-red text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-secondary mb-1" htmlFor="ret-id">
            Retraction ID (e.g. SYN-RET-004)
          </label>
          <input
            id="ret-id"
            type="text"
            value={retractionId}
            onChange={(e) => setRetractionId(e.target.value)}
            required
            className="w-full bg-bg border border-border rounded px-2.5 py-1.5 text-xs font-mono text-text focus-visible:ring-1 focus-visible:ring-accent"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-secondary mb-1" htmlFor="trial-id">
            Retracted Trial ID (e.g. SYN-TR-0004)
          </label>
          <input
            id="trial-id"
            type="text"
            value={trialId}
            onChange={(e) => setTrialId(e.target.value)}
            required
            className="w-full bg-bg border border-border rounded px-2.5 py-1.5 text-xs font-mono text-text focus-visible:ring-1 focus-visible:ring-accent"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-secondary mb-1" htmlFor="reason-cat">
            Reason Category
          </label>
          <select
            id="reason-cat"
            value={reasonCategory}
            onChange={(e) => setReasonCategory(e.target.value)}
            className="w-full bg-bg border border-border rounded px-2.5 py-1.5 text-xs text-text focus-visible:ring-1 focus-visible:ring-accent"
          >
            <option value="fabrication">Fabrication (weight: 1.0, critical safety floor)</option>
            <option value="error">Methodological / Calculation Error (weight: 0.6)</option>
            <option value="administrative">Administrative / Duplicate Publication (weight: 0.2)</option>
            <option value="unknown">Unknown (weight: 0.5)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-secondary mb-1" htmlFor="reason-text">
            Notice Reason Text
          </label>
          <textarea
            id="reason-text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            required
            className="w-full bg-bg border border-border rounded px-2.5 py-1.5 text-xs text-text focus-visible:ring-1 focus-visible:ring-accent"
          />
        </div>

        <div className="pt-2 flex items-center justify-end gap-2 border-t border-border">
          <button
            type="button"
            onClick={() => setIsNoticeModalOpen(false)}
            className="px-3 py-1.5 rounded text-xs font-medium text-secondary hover:text-text hover:bg-raised border border-border"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded text-xs font-medium bg-accent text-bg hover:opacity-90 flex items-center gap-1.5 disabled:opacity-50"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{isSubmitting ? 'Submitting...' : 'Queue Ingest Task'}</span>
          </button>
        </div>
      </form>
    </dialog>
  );
};
