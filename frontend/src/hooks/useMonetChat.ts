import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { sendMonetMessage, type MonetChatResponse, type TodoItem } from '../services/api';
import { getChatErrorMessage } from '../utils/chatErrors';
import { getUserTimeZone } from '../utils/timeZone';

export type MonetChatEntry = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  nutritionEntries?: MonetChatResponse['nutrition_entries'];
  todoItems?: TodoItem[];
  status?: 'pending' | 'final' | 'error';
};

const TODOS_QUERY_KEY = ['todos', 'list'];
const NUTRITION_SUMMARY_KEY = ['nutrition', 'summary'];
const NUTRITION_HISTORY_KEY = ['nutrition', 'history'];
const STORAGE_KEY = 'monet-chat-state';
const MAX_HISTORY = 60;

type StoredChat = {
  sessionId?: string;
  history: MonetChatEntry[];
};

const loadStoredChat = (): StoredChat | null => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredChat>;
    const history = Array.isArray(parsed.history) ? parsed.history.slice(-MAX_HISTORY) : [];
    const sessionId = typeof parsed.sessionId === 'string' ? parsed.sessionId : undefined;
    return { sessionId, history };
  } catch {
    return null;
  }
};

const persistChat = (state: StoredChat) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage failures (e.g., private mode).
  }
};

const buildFallbackReply = (response: MonetChatResponse) => {
  const todoItems = response.todo_items ?? [];
  const nutritionEntries = response.nutrition_entries ?? [];
  if (todoItems.length > 0 && nutritionEntries.length > 0) {
    return 'All set—your meal is logged and the tasks are tucked in.';
  }
  if (todoItems.length > 0) {
    return 'Consider it done. I added those tasks to your list.';
  }
  if (nutritionEntries.length > 0) {
    return 'Logged with care. Your meal is in the ledger.';
  }
  return 'Noted, and I’m here for the next step.';
};

export function useMonetChat() {
  const stored = useMemo(() => loadStoredChat(), []);
  const [sessionId, setSessionId] = useState<string | undefined>(() => stored?.sessionId);
  const [history, setHistory] = useState<MonetChatEntry[]>(() => stored?.history ?? []);
  const queryClient = useQueryClient();
  const timeZone = useMemo(() => getUserTimeZone(), []);

  const appendEntry = (entry: MonetChatEntry) => {
    setHistory((prev) => {
      const next = [...prev, entry];
      return next.slice(-MAX_HISTORY);
    });
  };

  useEffect(() => {
    const stableHistory = history.filter((entry) => entry.status !== 'pending');
    persistChat({ sessionId, history: stableHistory });
  }, [sessionId, history]);

  const mutation = useMutation({
    mutationFn: ({ message }: { message: string; pendingId: string }) =>
      sendMonetMessage({ message, session_id: sessionId, time_zone: timeZone }),
    onSuccess: (response, variables) => {
      const todoItems = response.todo_items ?? [];
      const nutritionEntries = response.nutrition_entries ?? [];
      const reply = response.reply?.trim() || buildFallbackReply(response);
      setSessionId(response.session_id);
      setHistory((prev) => {
        let replaced = false;
        const next = prev.map((entry) => {
          if (entry.id !== variables.pendingId) return entry;
          replaced = true;
          return {
            ...entry,
            text: reply,
            nutritionEntries,
            todoItems,
            status: 'final'
          };
        });
        if (!replaced) {
          next.push({
            id: crypto.randomUUID(),
            role: 'assistant',
            text: reply,
            nutritionEntries,
            todoItems,
            status: 'final'
          });
        }
        return next.slice(-MAX_HISTORY);
      });
      if (todoItems.length > 0) {
        queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
      }
      if (nutritionEntries.length > 0) {
        queryClient.invalidateQueries({ queryKey: NUTRITION_SUMMARY_KEY });
        queryClient.invalidateQueries({ queryKey: NUTRITION_HISTORY_KEY });
      }
    },
    onError: (error, variables) => {
      const message = getChatErrorMessage(error, 'I hit a snag—try that once more for me.');
      setHistory((prev) =>
        prev.map((entry) =>
          entry.id === variables.pendingId
            ? {
                ...entry,
                text: message,
                status: 'error'
              }
            : entry
        )
      );
    }
  });

  const sendMessage = async (message: string) => {
    const trimmed = message.trim();
    if (!trimmed) return;
    const pendingId = crypto.randomUUID();
    setHistory((prev) => {
      const next = [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', text: trimmed },
        { id: pendingId, role: 'assistant', text: '', status: 'pending' }
      ];
      return next.slice(-MAX_HISTORY);
    });
    await mutation.mutateAsync({ message: trimmed, pendingId });
  };

  return {
    sessionId,
    history,
    sendMessage,
    isSending: mutation.isPending,
    error: mutation.error
  };
}
