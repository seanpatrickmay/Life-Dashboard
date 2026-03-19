import { useState, useRef, useEffect } from 'react';
import styled, { keyframes, css } from 'styled-components';

import { useMonetChat } from '../../hooks/useMonetChat';
import { Z_LAYERS } from '../../styles/zLayers';

/* ── Animations ─────────────────────────────────────────────── */

const dotPulse = keyframes`
  0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
  40% { transform: translateY(-4px); opacity: 0.95; }
`;

const slideUp = keyframes`
  from { opacity: 0; transform: translateY(16px) scale(0.96); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
`;

const bubblePop = keyframes`
  0%   { transform: scale(0.6); opacity: 0; }
  70%  { transform: scale(1.08); }
  100% { transform: scale(1); opacity: 1; }
`;

/* ── Floating Bubble ────────────────────────────────────────── */

const BubbleButton = styled.button`
  position: fixed;
  bottom: 28px;
  right: 28px;
  z-index: ${Z_LAYERS.chatBubble};
  width: 58px;
  height: 58px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: ${({ theme }) =>
    theme.mode === 'dark' ? 'rgba(20, 28, 46, 0.88)' : 'rgba(248, 237, 212, 0.94)'};
  box-shadow:
    0 4px 20px rgba(8, 14, 28, 0.35),
    0 0 0 1px rgba(255, 255, 255, 0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  animation: ${bubblePop} 0.4s ease-out both;

  &:hover {
    transform: scale(1.08);
    box-shadow:
      0 6px 28px rgba(8, 14, 28, 0.45),
      0 0 0 1px rgba(255, 255, 255, 0.14);
  }

  &:active {
    transform: scale(0.96);
  }
`;

const BubbleIcon = styled.span<{ $open: boolean }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: ${({ $open }) => ($open ? '1.3rem' : '1.1rem')};
  letter-spacing: 0.06em;
  color: ${({ theme }) => theme.colors.textPrimary};
  user-select: none;
  transition: transform 0.2s ease;
  transform: ${({ $open }) => ($open ? 'rotate(45deg)' : 'none')};
`;

/* ── Chat Drawer ────────────────────────────────────────────── */

const Overlay = styled.div<{ $open: boolean }>`
  position: fixed;
  inset: 0;
  z-index: ${Z_LAYERS.chatBubble - 1};
  pointer-events: ${({ $open }) => ($open ? 'auto' : 'none')};
`;

const Drawer = styled.div<{ $open: boolean }>`
  position: fixed;
  bottom: 96px;
  right: 28px;
  z-index: ${Z_LAYERS.chatBubble};
  width: min(420px, calc(100vw - 40px));
  max-height: min(560px, calc(100vh - 140px));
  display: flex;
  flex-direction: column;
  border-radius: 22px;
  background: ${({ theme }) =>
    theme.mode === 'dark' ? 'rgba(20, 28, 46, 0.92)' : 'rgba(255, 255, 255, 0.92)'};
  border: 1px solid
    ${({ theme }) =>
      theme.mode === 'dark' ? 'rgba(246, 240, 232, 0.16)' : 'rgba(30, 31, 46, 0.12)'};
  box-shadow:
    0 16px 48px rgba(8, 14, 28, 0.4),
    0 0 0 1px rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  color: ${({ theme }) => theme.colors.textPrimary};
  overflow: hidden;
  animation: ${slideUp} 0.25s ease-out both;

  ${({ $open }) =>
    !$open &&
    css`
      display: none;
    `}
`;

const DrawerHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 10px;
  flex-shrink: 0;
  border-bottom: 1px solid
    ${({ theme }) =>
      theme.mode === 'dark' ? 'rgba(246, 240, 232, 0.08)' : 'rgba(30, 31, 46, 0.06)'};
`;

const DrawerTitle = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.82rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
`;

const CloseButton = styled.button`
  border: none;
  background: transparent;
  color: ${({ theme }) => theme.colors.textPrimary};
  opacity: 0.5;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 4px 6px;
  border-radius: 6px;
  transition: opacity 0.15s ease;

  &:hover {
    opacity: 0.9;
  }
`;

/* ── Chat Content ───────────────────────────────────────────── */

const History = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;

  &::-webkit-scrollbar { width: 3px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 2px;
  }
`;

const Message = styled.div<{ $role: 'user' | 'assistant' }>`
  align-self: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  max-width: 88%;
  padding: 10px 13px;
  border-radius: 14px;
  background: ${({ $role }) => ($role === 'user' ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.18)')};
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 0.85rem;
  line-height: 1.45;
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const RoleLabel = styled.span<{ $role: 'user' | 'assistant' }>`
  font-size: 0.58rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  opacity: 0.65;
  color: ${({ $role }) => ($role === 'assistant' ? 'rgba(248, 236, 200, 0.92)' : 'rgba(255, 255, 255, 0.75)')};
`;

const ThinkingDots = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 5px;

  span {
    width: 5px;
    height: 5px;
    border-radius: 999px;
    background: rgba(248, 236, 200, 0.9);
    animation: ${dotPulse} 1.1s ease-in-out infinite;
  }

  span:nth-child(2) { animation-delay: 0.15s; }
  span:nth-child(3) { animation-delay: 0.3s; }
`;

const MetaList = styled.ul`
  margin: 0;
  padding-left: 16px;
  font-size: 0.76rem;
  opacity: 0.9;
`;

const MetaBadge = styled.span`
  font-size: 0.62rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.7;
`;

/* ── Input Form ─────────────────────────────────────────────── */

const Form = styled.form`
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 10px 14px 14px;
  border-top: 1px solid
    ${({ theme }) =>
      theme.mode === 'dark' ? 'rgba(246, 240, 232, 0.08)' : 'rgba(30, 31, 46, 0.06)'};
`;

const Input = styled.textarea`
  flex: 1;
  min-height: 42px;
  max-height: 100px;
  resize: none;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.12);
  padding: 9px 11px;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.85rem;
  line-height: 1.4;

  &::placeholder {
    opacity: 0.4;
  }
`;

const SendButton = styled.button`
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  background: ${({ theme }) => theme.palette?.ember?.['200'] ?? '#f5d37c'};
  color: ${({ theme }) => theme.colors.backgroundPage};
  flex-shrink: 0;
  transition: opacity 0.15s ease;

  &:disabled {
    opacity: 0.5;
    cursor: default;
  }
`;

/* ── Component ──────────────────────────────────────────────── */

export function MonetChatBubble() {
  const { history, sendMessage, isSending } = useMonetChat();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const historyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (open && historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight;
    }
  }, [history.length, open]);

  // Focus input when drawer opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  const submit = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setText('');
    await sendMessage(trimmed);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await submit();
  };

  const renderMeta = (entry: (typeof history)[number]) => {
    const rows: JSX.Element[] = [];
    if (entry.nutritionEntries && entry.nutritionEntries.length > 0) {
      rows.push(
        <MetaList key={`${entry.id}-nutrition`}>
          <li><MetaBadge>Nutrition</MetaBadge></li>
          {entry.nutritionEntries.map((item, index) => (
            <li key={`${entry.id}-nut-${index}`}>
              Logged {item.quantity} {item.unit} {item.food_name ?? ''} ({item.status})
            </li>
          ))}
        </MetaList>
      );
    }
    if (entry.todoItems && entry.todoItems.length > 0) {
      rows.push(
        <MetaList key={`${entry.id}-todos`}>
          <li><MetaBadge>Tasks</MetaBadge></li>
          {entry.todoItems.map((item) => (
            <li key={`${entry.id}-todo-${item.id}`}>
              Added &ldquo;{item.text}&rdquo;
              {item.deadline_utc ? ` — due ${new Date(item.deadline_utc).toLocaleString()}` : ''}
            </li>
          ))}
        </MetaList>
      );
    }
    return rows;
  };

  return (
    <>
      {/* Backdrop to close on outside click */}
      <Overlay $open={open} onClick={() => setOpen(false)} />

      {/* Chat drawer */}
      <Drawer $open={open}>
        <DrawerHeader>
          <DrawerTitle>Monet</DrawerTitle>
          <CloseButton type="button" onClick={() => setOpen(false)} aria-label="Close chat">
            &times;
          </CloseButton>
        </DrawerHeader>

        <History ref={historyRef}>
          {history.length === 0 && (
            <Message $role="assistant">
              <RoleLabel $role="assistant">Monet</RoleLabel>
              Ask me anything about your day, nutrition, or tasks&mdash;and I&rsquo;ll log meals or create to-dos when needed.
            </Message>
          )}
          {history.slice(-20).map((entry) => (
            <Message key={entry.id} $role={entry.role}>
              <RoleLabel $role={entry.role}>{entry.role === 'assistant' ? 'Monet' : 'You'}</RoleLabel>
              {entry.status === 'pending' ? (
                <ThinkingDots aria-label="Monet is thinking">
                  <span />
                  <span />
                  <span />
                </ThinkingDots>
              ) : (
                <span>{entry.text}</span>
              )}
              {entry.role === 'assistant' ? renderMeta(entry) : null}
            </Message>
          ))}
        </History>

        <Form onSubmit={handleSubmit}>
          <Input
            ref={inputRef}
            placeholder="Ask Monet anything..."
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={async (event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                await submit();
              }
            }}
          />
          <SendButton type="submit" disabled={isSending}>
            {isSending ? '...' : 'Send'}
          </SendButton>
        </Form>
      </Drawer>

      {/* Floating bubble */}
      <BubbleButton
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={open ? 'Close Monet chat' : 'Open Monet chat'}
      >
        <BubbleIcon $open={open}>{open ? '+' : 'M'}</BubbleIcon>
      </BubbleButton>
    </>
  );
}
