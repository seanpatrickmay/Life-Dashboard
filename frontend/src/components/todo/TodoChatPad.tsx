import { useState } from 'react';
import styled from 'styled-components';
import { useTodoClaudeChat } from '../../hooks/useTodoClaudeChat';

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
`;

const Heading = styled.h3`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(0.9rem, 1.8vw, 1.1rem);
  letter-spacing: 0.14em;
  text-transform: uppercase;
`;

const History = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 180px;
  overflow-y: auto;
  padding-right: 4px;
`;

const Message = styled.div<{ $role: 'user' | 'assistant' }>`
  align-self: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  max-width: 88%;
  padding: 8px 10px;
  border-radius: 14px;
  font-size: 0.86rem;
  background: ${({ $role, theme }) =>
    $role === 'user' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.22)'};
  border: 1px solid rgba(255, 255, 255, 0.16);
`;

const MetaList = styled.ul`
  margin: 6px 0 0;
  padding-left: 16px;
  font-size: 0.78rem;
  opacity: 0.85;
`;

const Form = styled.form`
  display: flex;
  gap: 8px;
  margin-top: 4px;
`;

const Input = styled.textarea`
  flex: 1;
  min-height: 44px;
  max-height: 72px;
  resize: none;
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(0, 0, 0, 0.18);
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.85rem;
`;

const Button = styled.button`
  border: 0;
  border-radius: 12px;
  padding: 10px 12px;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  cursor: pointer;
  background: ${({ theme }) => theme.colors.accent ?? '#f5d37c'};
  color: ${({ theme }) => theme.colors.backgroundPage};
`;

export function TodoChatPad() {
  const { history, sendMessage, isSending } = useTodoClaudeChat();
  const [text, setText] = useState('');

  const submit = async () => {
    if (!text.trim()) return;
    await sendMessage(text.trim());
    setText('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await submit();
  };

  return (
    <Wrapper>
      <Heading data-halo="heading">Monet • Tasks</Heading>
      <History>
        {history.length === 0 && (
          <Message $role="assistant">
            Tell me what you&apos;d like to remember, like &quot;Pay rent by Friday 5pm&quot; or &quot;Do the laundry&quot;.
          </Message>
        )}
        {history.map((entry) => (
          <Message key={entry.id} $role={entry.role}>
            {entry.text}
            {entry.meta && entry.meta.length > 0 && (
              <MetaList>
                {entry.meta.map((item) => (
                  <li key={item.id}>
                    {item.text}
                    {item.deadline_utc ? ` — due ${new Date(item.deadline_utc).toLocaleString()}` : ' — no deadline'}
                  </li>
                ))}
              </MetaList>
            )}
          </Message>
        ))}
      </History>
      <Form onSubmit={handleSubmit}>
        <Input
          placeholder="e.g. Draft trip packing list by Thursday evening"
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
    </Wrapper>
  );
}
