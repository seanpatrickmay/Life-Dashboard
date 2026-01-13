import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { sendClaudeMessage, type ClaudeChatResponse } from '../services/api';
import { getChatErrorMessage } from '../utils/chatErrors';

export type ChatEntry = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  meta?: ClaudeChatResponse['logged_entries'];
};

export function useClaudeChat() {
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [history, setHistory] = useState<ChatEntry[]>([]);

  const mutation = useMutation({
    mutationFn: (message: string) => sendClaudeMessage(message, sessionId),
    onSuccess: (response, variables) => {
      setSessionId(response.session_id);
      setHistory((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', text: variables },
        { id: crypto.randomUUID(), role: 'assistant', text: response.reply, meta: response.logged_entries }
      ]);
    },
    onError: (error, variables) => {
      const message = getChatErrorMessage(error, 'I ran into an issue—try again in a moment.');
      setHistory((prev) => [...prev, { id: crypto.randomUUID(), role: 'assistant', text: message }]);
    }
  });

  const sendMessage = async (message: string) => {
    setHistory((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text: message }]);
    await mutation.mutateAsync(message);
  };

  return {
    sessionId,
    history,
    sendMessage,
    isSending: mutation.isPending,
    error: mutation.error
  };
}
