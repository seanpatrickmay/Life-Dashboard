import { useState } from 'react';
import styled from 'styled-components';
import { Card } from '../common/Card';
import { useNutritionChat } from '../../hooks/useNutritionChat';
import { focusRing } from '../../styles/animations';

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
  background: ${({ $role, theme }) => ($role === 'user' ? theme.colors.overlay : theme.colors.surfaceRaised)};
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
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 12px;
  padding: 10px 12px;
  font-family: ${({ theme }) => theme.fonts.body};
  color: ${({ theme }) => theme.colors.textPrimary};
  ${focusRing}
`;

const Button = styled.button`
  background: ${({ theme }) => theme.palette?.ember?.['200'] ?? '#f5d37c'};
  color: ${({ theme }) => theme.colors.backgroundPage};
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.1em;
  border: 0;
  border-radius: 12px;
  padding: 12px 16px;
  cursor: pointer;
  ${focusRing}
`;

export function NutritionChatPanel() {
  const { history, sendMessage, isSending } = useNutritionChat();
  const [text, setText] = useState('');

  const submit = async () => {
    if (!text.trim()) return;
    await sendMessage(text.trim());
    setText('');
  };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await submit();
  };

  return (
    <Panel>
      <h3 data-halo="heading">Monet • Nutrition Mentor</h3>
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
