import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import styled, { keyframes, css } from 'styled-components';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ToastType = 'error' | 'success' | 'info';

type ToastEntry = {
  id: number;
  message: string;
  type: ToastType;
  exiting: boolean;
};

type AddToastFn = (message: string, type?: ToastType) => void;

// ---------------------------------------------------------------------------
// Module-level emitter
// ---------------------------------------------------------------------------
// QueryClient is created outside the React tree, so we expose a stable
// callback ref that the ToastProvider sets once it mounts. Callers use
// `emitToast()` which safely no-ops if the provider hasn't mounted yet.

let _emitRef: AddToastFn | null = null;

export function emitToast(message: string, type: ToastType = 'error'): void {
  _emitRef?.(message, type);
}

// ---------------------------------------------------------------------------
// Context (for components that want to call addToast via hook)
// ---------------------------------------------------------------------------

const ToastContext = createContext<{ addToast: AddToastFn } | null>(null);

export function useToast(): { addToast: AddToastFn } {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}

// ---------------------------------------------------------------------------
// Auto-dismiss duration & dedup window
// ---------------------------------------------------------------------------

const DISMISS_MS = 5_000;
const EXIT_MS = 280;
const DEDUP_WINDOW_MS = 2_000;
const MAX_TOASTS = 5;

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const nextId = useRef(0);
  const recentMessages = useRef<Map<string, number>>(new Map());
  const timerIds = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  const addToast: AddToastFn = useCallback((message, type = 'error') => {
    const now = Date.now();

    // Deduplicate: skip if same message was shown within the dedup window
    const lastShown = recentMessages.current.get(message);
    if (lastShown !== undefined && now - lastShown < DEDUP_WINDOW_MS) {
      return;
    }
    recentMessages.current.set(message, now);

    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, message, type, exiting: false }]);

    // Auto-dismiss
    const dismissTimer = setTimeout(() => {
      // Start exit animation
      setToasts((prev) =>
        prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)),
      );
      timerIds.current.delete(dismissTimer);
      // Remove after animation completes
      const removeTimer = setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        timerIds.current.delete(removeTimer);
      }, EXIT_MS);
      timerIds.current.add(removeTimer);
    }, DISMISS_MS);
    timerIds.current.add(dismissTimer);
  }, []);

  // Register/unregister module-level emitter
  useEffect(() => {
    _emitRef = addToast;
    return () => {
      _emitRef = null;
    };
  }, [addToast]);

  // Clean up all timers on unmount
  useEffect(() => {
    const timers = timerIds.current;
    return () => {
      for (const id of timers) clearTimeout(id);
      timers.clear();
    };
  }, []);

  // Prune old dedup entries periodically to avoid unbounded growth
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const map = recentMessages.current;
      for (const [key, ts] of map) {
        if (now - ts > DEDUP_WINDOW_MS * 3) map.delete(key);
      }
    }, 10_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      {toasts.length > 0 && (
        <ToastContainer role="log" aria-live="assertive">
          {toasts.slice(-MAX_TOASTS).map((t) => (
            <ToastItem key={t.id} $type={t.type} $exiting={t.exiting} role="alert">
              {t.message}
            </ToastItem>
          ))}
        </ToastContainer>
      )}
    </ToastContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Styled components
// ---------------------------------------------------------------------------

const fadeSlideIn = keyframes`
  from {
    opacity: 0;
    transform: translateX(24px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
`;

const fadeSlideOut = keyframes`
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(24px);
  }
`;

const ToastContainer = styled.div`
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
  max-width: min(400px, calc(100vw - 48px));
`;

function accentColor(type: ToastType): string {
  switch (type) {
    case 'error':
      return 'rgba(242, 140, 60, 0.85)';
    case 'success':
      return 'rgba(63, 155, 138, 0.85)';
    case 'info':
      return 'rgba(126, 215, 196, 0.85)';
  }
}

function borderColor(type: ToastType): string {
  switch (type) {
    case 'error':
      return 'rgba(242, 140, 60, 0.35)';
    case 'success':
      return 'rgba(63, 155, 138, 0.30)';
    case 'info':
      return 'rgba(126, 215, 196, 0.30)';
  }
}

const ToastItem = styled.div<{ $type: ToastType; $exiting: boolean }>`
  padding: 12px 18px;
  border-radius: ${({ theme }) => theme.radii.card};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.85rem;
  line-height: 1.45;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: ${({ theme }) =>
    theme.mode === 'dark'
      ? 'rgba(20, 28, 46, 0.82)'
      : 'rgba(255, 255, 255, 0.82)'};
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid ${({ $type }) => borderColor($type)};
  border-left: 3px solid ${({ $type }) => accentColor($type)};
  box-shadow: ${({ theme }) => theme.shadows.soft};
  pointer-events: auto;

  ${({ $exiting }) =>
    $exiting
      ? css`
          animation: ${fadeSlideOut} ${EXIT_MS}ms ease-in forwards;
        `
      : css`
          animation: ${fadeSlideIn} 280ms ease-out;
        `}
`;
