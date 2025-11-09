import { useState } from 'react';
import styled from 'styled-components';
import { Card } from '../common/Card';
import { useClaudeChat } from '../../hooks/useClaudeChat';

const Panel = styled(Card)`
  min-height: 260px;
`;

const History = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 320px;
  overflow-y: auto;
`;

const Entry = styled.div<{ $role: 'user' | 'assistant' }>`
  align-self: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 16px;
  background: ${({ $role }) => ($role === 'user' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.15)')};
  font-size: 0.92rem;
`;

const Form = styled.form`
  margin-top: 16px;
  display: flex;
  gap: 12px;
`;

const Input = styled.textarea`
  flex: 1;
  min-height: 60px;
  background: rgba(0,0,0,0.08);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 12px;
  padding: 10px 12px;
  font-family: ${({ theme }) => theme.fonts.body};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const Button = styled.button`
  background: ${({ theme }) => theme.colors.accent};
  color: ${({ theme }) => theme.colors.backgroundPage};
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.1em;
  border: 0;
  border-radius: 12px;
  padding: 12px 16px;
  cursor: pointer;
`;

export function ClaudeChatPanel() {
  const { history, sendMessage, isSending } = useClaudeChat();
  const [text, setText] = useState('');

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    await sendMessage(text.trim());
    setText('');
  };

  return (
    <Panel>
      <h3 data-halo="heading">Claude • Nutrition Mentor</h3>
      <History>
        {history.length === 0 && <Entry $role="assistant">Tell me what you ate today and I’ll log it.</Entry>}
        {history.map((entry) => (
          <Entry key={entry.id} $role={entry.role}>
            {entry.text}
            {entry.meta && entry.meta.length > 0 && (
              <ul>
                {entry.meta.map((item, idx) => (
                  <li key={idx}>
                    {item.quantity} {item.unit} {item.food_name} ({item.status})
                  </li>
                ))}
              </ul>
            )}
          </Entry>
        ))}
      </History>
      <Form onSubmit={onSubmit}>
        <Input
          placeholder="e.g. I had 1 cup oatmeal and 1 tbsp chia seeds"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <Button type="submit" disabled={isSending}>
          {isSending ? '...' : 'Send'}
        </Button>
      </Form>
    </Panel>
  );
}
