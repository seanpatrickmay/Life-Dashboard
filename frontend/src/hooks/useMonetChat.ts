import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { isGuestMode } from '../demo/guest/guestMode';
import { getGuestTodos } from '../demo/guest/guestStore';
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
const STORAGE_KEY_DEFAULT = 'monet-chat-state';
const STORAGE_KEY_GUEST = 'monet-chat-state-guest';
const MAX_HISTORY = 60;

type StoredChat = {
  sessionId?: string;
  dayKey?: string;
  history: MonetChatEntry[];
};

const formatLocalDayKey = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const loadStoredChat = (storageKey: string, expectedDayKey?: string): StoredChat | null => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredChat>;
    const history = Array.isArray(parsed.history) ? parsed.history.slice(-MAX_HISTORY) : [];
    const sessionId = typeof parsed.sessionId === 'string' ? parsed.sessionId : undefined;
    const dayKey = typeof parsed.dayKey === 'string' ? parsed.dayKey : undefined;
    if (expectedDayKey && dayKey !== expectedDayKey) return null;
    return { sessionId, dayKey, history };
  } catch {
    return null;
  }
};

const persistChat = (storageKey: string, state: StoredChat) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(state));
  } catch {
    // Ignore storage failures (e.g., private mode).
  }
};

const buildGuestSeedChat = (dayKey: string): StoredChat => {
  const todos = getGuestTodos();
  const insuranceTodo =
    todos.find((item) => item.id === 109) ??
    todos.find((item) => item.text.toLowerCase().includes('call insurance'));
  const physicalTodo =
    todos.find((item) => item.text.toLowerCase().includes('annual physical')) ??
    todos.find((item) => item.text.toLowerCase().includes('schedule annual'));

  const nutritionEntries: MonetChatResponse['nutrition_entries'] = [
    {
      ingredient_id: 9003,
      food_name: 'Chicken burrito bowl',
      quantity: 1,
      unit: 'serving',
      status: 'logged',
      created: false
    }
  ];

  return {
    dayKey,
    sessionId: 'guest-demo-session',
    history: [
      {
        id: 'guest-seed-1',
        role: 'assistant',
        text:
          'Welcome to Guest mode. I can log meals and turn notes into tasks locally (no backend). Try: “Log: …” or “Remind me to …”.',
        status: 'final'
      },
      {
        id: 'guest-seed-2',
        role: 'user',
        text: 'Lunch was a chicken burrito bowl. Remind me to call insurance tomorrow morning about labs coverage.'
      },
      {
        id: 'guest-seed-3',
        role: 'assistant',
        text: 'Done. Logged lunch and added an admin reminder. If you tell me when, I’ll attach a due time.',
        nutritionEntries,
        todoItems: insuranceTodo ? [insuranceTodo] : [],
        status: 'final'
      },
      { id: 'guest-seed-4', role: 'user', text: 'Also: schedule my annual physical + labs next week.' },
      {
        id: 'guest-seed-5',
        role: 'assistant',
        text: 'Added. Want it with your PCP, or should I treat this as “find in-network provider + book”?',
        todoItems: physicalTodo ? [physicalTodo] : [],
        status: 'final'
      }
    ].slice(-MAX_HISTORY)
  };
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
  const guest = useMemo(() => isGuestMode(), []);
  const dayKey = useMemo(() => formatLocalDayKey(new Date()), []);
  const storageKey = guest ? STORAGE_KEY_GUEST : STORAGE_KEY_DEFAULT;
  const stored = useMemo(
    () => loadStoredChat(storageKey, guest ? dayKey : undefined),
    [storageKey, guest, dayKey]
  );
  const initial = useMemo(() => {
    if (stored) return stored;
    if (guest) return buildGuestSeedChat(dayKey);
    return { sessionId: undefined, history: [] } satisfies StoredChat;
  }, [stored, guest, dayKey]);

  const [sessionId, setSessionId] = useState<string | undefined>(() => initial.sessionId);
  const [history, setHistory] = useState<MonetChatEntry[]>(() => initial.history);
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
    persistChat(storageKey, { sessionId, dayKey: guest ? dayKey : undefined, history: stableHistory });
  }, [sessionId, history, storageKey, guest, dayKey]);

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
