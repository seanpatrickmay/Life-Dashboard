import { useState } from 'react';
import styled, { keyframes } from 'styled-components';

import { Card } from '../common/Card';
import { useMonetChat } from '../../hooks/useMonetChat';

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 2vw, 18px);
  height: clamp(340px, 45vh, 520px);
`;

const Heading = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.95rem, 2.2vw, 1.1rem);
  letter-spacing: 0.18em;
  text-transform: uppercase;
`;

const History = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
`;

const Message = styled.div<{ $role: 'user' | 'assistant' }>`
  align-self: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 16px;
  background: ${({ $role }) => ($role === 'user' ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.22)')};
  border: 1px solid rgba(255, 255, 255, 0.14);
  font-size: 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const RoleLabel = styled.span<{ $role: 'user' | 'assistant' }>`
  font-size: 0.62rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  opacity: 0.7;
  color: ${({ $role }) => ($role === 'assistant' ? 'rgba(248, 236, 200, 0.92)' : 'rgba(255, 255, 255, 0.75)')};
`;

const dotPulse = keyframes`
  0%, 80%, 100% { transform: translateY(0); opacity: 0.45; }
  40% { transform: translateY(-4px); opacity: 0.95; }
`;

const ThinkingDots = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 6px;

  span {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: rgba(248, 236, 200, 0.9);
    animation: ${dotPulse} 1.1s ease-in-out infinite;
  }

  span:nth-child(2) {
    animation-delay: 0.15s;
  }

  span:nth-child(3) {
    animation-delay: 0.3s;
  }
`;

const MetaList = styled.ul`
  margin: 0;
  padding-left: 18px;
  font-size: 0.8rem;
  opacity: 0.9;
`;

const MetaBadge = styled.span`
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.7;
`;

const Form = styled.form`
  display: flex;
  gap: 12px;
  align-items: flex-start;
`;

const Input = styled.textarea`
  flex: 1;
  min-height: 60px;
  max-height: 120px;
  resize: none;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(0, 0, 0, 0.18);
  padding: 10px 12px;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.9rem;
`;

const Button = styled.button`
  border: none;
  border-radius: 14px;
  padding: 12px 18px;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  cursor: pointer;
  background: ${({ theme }) => theme.colors.accent ?? '#f5d37c'};
  color: ${({ theme }) => theme.colors.backgroundPage};
`;

export function MonetChatPanel() {
  const { history, sendMessage, isSending } = useMonetChat();
  const [text, setText] = useState('');

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
          <li>
            <MetaBadge>Nutrition</MetaBadge>
          </li>
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
          <li>
            <MetaBadge>Tasks</MetaBadge>
          </li>
          {entry.todoItems.map((item) => (
            <li key={`${entry.id}-todo-${item.id}`}>
              Added “{item.text}”
              {item.deadline_utc ? ` — due ${new Date(item.deadline_utc).toLocaleString()}` : ''}
            </li>
          ))}
        </MetaList>
      );
    }
    return rows;
  };

  return (
    <Panel>
      <Heading data-halo="heading">Monet • Today</Heading>
      <History>
        {history.length === 0 && (
          <Message $role="assistant">
            <RoleLabel $role="assistant">Monet</RoleLabel>
            Ask me anything about your day, nutrition, or tasks—and I&apos;ll log meals or create to-dos when needed.
          </Message>
        )}
        {history.map((entry) => (
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
          placeholder="e.g. Logged avocado toast, remind me to call the bank tomorrow"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={async (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              await submit();
            }
          }}
        />
        <Button type="submit" disabled={isSending}>
          {isSending ? '...' : 'Send'}
        </Button>
      </Form>
    </Panel>
  );
}
