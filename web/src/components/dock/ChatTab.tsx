import React, { useState } from 'react';
import { useUiStore } from '../../store/uiStore';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';
import { Send, User, Bot } from 'lucide-react';
import type { ChatMessage } from '../../api/types';

export const ChatTab: React.FC = () => {
  const { tenant, sessionId, setSessionId } = useUiStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');

  const chatMutation = useMutation({
    mutationFn: (text: string) => api.sendChat({ tenant, message: text, session_id: sessionId }),
    onSuccess: (data) => {
      setSessionId(data.session_id);
      setMessages(data.messages);
      setInput('');
    },
  });

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || chatMutation.isPending) return;
    chatMutation.mutate(input.trim());
  };

  return (
    <div className="h-full flex flex-col p-3 overflow-hidden bg-surface select-none">
      <div tabIndex={0} role="log" aria-label="Team Chat Messages" className="flex-1 overflow-y-auto space-y-2 p-2 rounded border border-border bg-bg mb-2 focus-visible:ring-1 focus-visible:ring-accent">
        {messages.length === 0 && (
          <div className="text-center text-xs text-muted py-8">
            Team chat memory is persisted to your tenant graph in FalkorDB. Ask a question to coordinate evidence review.
          </div>
        )}

        {messages.map((m) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={m.id}
              className={`flex items-start gap-2 text-xs ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              {!isUser && (
                <div className="w-6 h-6 rounded bg-raised border border-border flex items-center justify-center flex-shrink-0 text-accent">
                  <Bot className="w-3.5 h-3.5" />
                </div>
              )}

              <div
                className={`max-w-[70%] p-2 rounded text-xs leading-relaxed ${
                  isUser
                    ? 'bg-accent text-bg font-medium'
                    : 'bg-raised border border-border text-text'
                }`}
              >
                {m.text}
              </div>

              {isUser && (
                <div className="w-6 h-6 rounded bg-raised border border-border flex items-center justify-center flex-shrink-0 text-secondary">
                  <User className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <form onSubmit={handleSend} className="flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Message ${tenant} team chat...`}
          className="flex-1 bg-bg border border-border rounded px-3 py-1.5 text-xs text-text focus-visible:ring-1 focus-visible:ring-accent"
        />
        <button
          type="submit"
          disabled={!input.trim() || chatMutation.isPending}
          className="px-3 py-1.5 rounded bg-accent text-bg hover:opacity-90 font-medium text-xs flex items-center gap-1 disabled:opacity-50"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Send</span>
        </button>
      </form>
    </div>
  );
};
