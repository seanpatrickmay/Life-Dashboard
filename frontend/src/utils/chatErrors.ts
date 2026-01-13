import axios from 'axios';

const formatResetTime = (iso?: string): string | null => {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

export const getChatErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error) && error.response?.status === 429) {
    const detail = error.response?.data?.detail;
    const reset = formatResetTime(detail?.reset_at);
    return reset ? `Daily limit reached. Try again after ${reset}.` : 'Daily chat limit reached.';
  }
  return fallback;
};
