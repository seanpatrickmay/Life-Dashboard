import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { sendClaudeTodoMessage, type ClaudeTodoResponse } from '../services/api';

export type TodoChatEntry = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  meta?: ClaudeTodoResponse['created_items'];
};

const TODOS_QUERY_KEY = ['todos', 'list'];

export function useTodoClaudeChat() {
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [history, setHistory] = useState<TodoChatEntry[]>([]);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (message: string) => sendClaudeTodoMessage(message, sessionId),
    onSuccess: (response, variables) => {
      setSessionId(response.session_id);
      setHistory((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', text: variables },
        { id: crypto.randomUUID(), role: 'assistant', text: response.reply, meta: response.created_items }
      ]);
      queryClient.invalidateQueries({ queryKey: TODOS_QUERY_KEY });
    }
  });

  const sendMessage = async (message: string) => {
    const trimmed = message.trim();
    if (!trimmed) return;
    setHistory((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text: trimmed }]);
    await mutation.mutateAsync(trimmed);
  };

  return {
    sessionId,
    history,
    sendMessage,
    isSending: mutation.isPending,
    error: mutation.error
  };
}

