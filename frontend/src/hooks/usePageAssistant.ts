import { useMemo, useState } from 'react';

import {
  sendMonetMessage,
  type AssistantAction,
  type AssistantPageContext,
} from '../services/api';
import { getChatErrorMessage } from '../utils/chatErrors';
import { getUserTimeZone } from '../utils/timeZone';

export type PageAssistantHistoryEntry = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  status?: 'pending' | 'final' | 'error';
};

export type PendingAssistantPlan = {
  planId: string | null;
  actions: AssistantAction[];
};

export function usePageAssistant(options: {
  context: AssistantPageContext;
  onActionsApplied?: () => void;
}) {
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [history, setHistory] = useState<PageAssistantHistoryEntry[]>([]);
  const [pendingPlan, setPendingPlan] = useState<PendingAssistantPlan | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const timeZone = useMemo(() => getUserTimeZone(), []);

  const sendMessage = async (message: string) => {
    const trimmed = message.trim();
    if (!trimmed || isSending || isApplying) return;
    const pendingId = crypto.randomUUID();
    setIsSending(true);
    setHistory((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', text: trimmed },
      { id: pendingId, role: 'assistant', text: '', status: 'pending' },
    ]);

    try {
      const response = await sendMonetMessage({
        message: trimmed,
        session_id: sessionId,
        time_zone: timeZone,
        page_context: options.context,
        execution_mode: 'preview',
      });
      setSessionId(response.session_id);
      setHistory((prev) =>
        prev.map((entry) =>
          entry.id === pendingId
            ? {
                ...entry,
                text: response.reply?.trim() || 'I can handle that. Confirm to continue.',
                status: 'final',
              }
            : entry,
        ),
      );
      const actions = response.proposed_actions ?? [];
      if (response.requires_confirmation && actions.length > 0) {
        setPendingPlan({
          planId: response.action_plan_id ?? null,
          actions,
        });
      } else {
        setPendingPlan(null);
      }
    } catch (error) {
      const fallback = getChatErrorMessage(error, 'I hit a snag while planning that action.');
      setHistory((prev) =>
        prev.map((entry) => (entry.id === pendingId ? { ...entry, text: fallback, status: 'error' } : entry)),
      );
    } finally {
      setIsSending(false);
    }
  };

  const cancelPlan = () => {
    if (!pendingPlan) return;
    setPendingPlan(null);
    setHistory((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'assistant', text: 'Canceled. I did not apply any changes.', status: 'final' },
    ]);
  };

  const confirmPlan = async () => {
    if (!pendingPlan || isApplying) return;
    const pendingId = crypto.randomUUID();
    setIsApplying(true);
    setHistory((prev) => [...prev, { id: pendingId, role: 'assistant', text: '', status: 'pending' }]);

    try {
      const response = await sendMonetMessage({
        message: 'Confirm these actions.',
        session_id: sessionId,
        time_zone: timeZone,
        page_context: options.context,
        execution_mode: 'commit',
        proposed_actions: pendingPlan.actions,
      });
      setSessionId(response.session_id);
      setHistory((prev) =>
        prev.map((entry) =>
          entry.id === pendingId
            ? {
                ...entry,
                text: response.reply?.trim() || 'Done.',
                status: 'final',
              }
            : entry,
        ),
      );
      setPendingPlan(null);
      options.onActionsApplied?.();
    } catch (error) {
      const fallback = getChatErrorMessage(error, 'I could not apply those actions.');
      setHistory((prev) =>
        prev.map((entry) => (entry.id === pendingId ? { ...entry, text: fallback, status: 'error' } : entry)),
      );
    } finally {
      setIsApplying(false);
    }
  };

  return {
    history,
    sessionId,
    pendingPlan,
    isSending,
    isApplying,
    sendMessage,
    confirmPlan,
    cancelPlan,
  };
}
