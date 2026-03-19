import { useEffect, useState } from 'react';
import styled from 'styled-components';

import { Card } from '../common/Card';
import { usePageAssistant } from '../../hooks/usePageAssistant';
import type { AssistantPageContext } from '../../services/api';
import { focusRing } from '../../styles/animations';

const Panel = styled(Card)`
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 360px;
  max-height: min(760px, calc(100vh - 180px));
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
`;

const Title = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
`;

const CollapseButton = styled.button`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textPrimary};
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.66rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  cursor: pointer;
  ${focusRing}
`;

const Body = styled.div<{ $collapsed: boolean }>`
  display: ${({ $collapsed }) => ($collapsed ? 'none' : 'grid')};
  gap: 12px;
  min-height: 0;
  flex: 1;
`;

const History = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  min-height: 150px;
  max-height: min(420px, calc(100vh - 360px));
`;

const Message = styled.div<{ $role: 'user' | 'assistant' }>`
  align-self: ${({ $role }) => ($role === 'user' ? 'flex-end' : 'flex-start')};
  max-width: 92%;
  border-radius: 14px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ $role, theme }) => ($role === 'user' ? theme.colors.overlay : theme.colors.surfaceRaised)};
  padding: 10px 12px;
  font-size: 0.88rem;
  white-space: pre-wrap;
`;

const PlanBox = styled.div`
  border: 1px solid ${({ theme }) => theme.colors.accent};
  background: ${({ theme }) => theme.colors.accentSubtle};
  border-radius: 12px;
  padding: 10px;
  display: grid;
  gap: 8px;
`;

const PlanTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
`;

const PlanList = styled.ul`
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
  font-size: 0.8rem;
`;

const ActionRow = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
`;

const Button = styled.button`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textPrimary};
  border-radius: 999px;
  padding: 7px 12px;
  cursor: pointer;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-size: 0.65rem;
  ${focusRing}

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
`;

const DangerButton = styled(Button)`
  border-color: ${({ theme }) => theme.colors.danger};
  background: ${({ theme }) => theme.colors.dangerSubtle};
`;

const Form = styled.form`
  display: grid;
  gap: 8px;
`;

const Input = styled.textarea`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border-radius: 10px;
  color: ${({ theme }) => theme.colors.textPrimary};
  padding: 8px 10px;
  min-height: 72px;
  resize: vertical;
  ${focusRing}
`;

const formatAction = (actionType: string, params: Record<string, unknown>) => {
  if (actionType === 'calendar.create_event') {
    return `Create event “${String(params.summary ?? 'Untitled')}”`;
  }
  if (actionType === 'calendar.update_event') {
    return `Update event #${String(params.event_id ?? 'selected')}`;
  }
  if (actionType === 'projects.create_todo') {
    return `Create todo “${String(params.text ?? '')}”`;
  }
  if (actionType === 'projects.create_note') {
    return `Create note “${String(params.title ?? 'Untitled')}”`;
  }
  if (actionType === 'projects.update_note') {
    return `Update note #${String(params.note_id ?? 'selected')}`;
  }
  return actionType;
};

export function PageAssistantPanel(props: {
  title: string;
  placeholder: string;
  context: AssistantPageContext;
  onActionsApplied?: () => void;
}) {
  const [text, setText] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const { history, pendingPlan, isSending, isApplying, sendMessage, confirmPlan, cancelPlan } = usePageAssistant({
    context: props.context,
    onActionsApplied: props.onActionsApplied,
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleResize = () => {
      setCollapsed(window.innerWidth < 980);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const submit = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setText('');
    await sendMessage(trimmed);
  };

  return (
    <Panel>
      <Header>
        <Title data-halo="heading">{props.title}</Title>
        <CollapseButton type="button" onClick={() => setCollapsed((prev) => !prev)}>
          {collapsed ? 'Open' : 'Hide'}
        </CollapseButton>
      </Header>
      <Body $collapsed={collapsed}>
        <History>
          {history.length === 0 ? (
            <Message $role="assistant">
              I can help with actions on this page and will always preview changes before applying them.
            </Message>
          ) : null}
          {history.map((entry) => (
            <Message key={entry.id} $role={entry.role}>
              {entry.status === 'pending' ? '...' : entry.text}
            </Message>
          ))}
        </History>

        {pendingPlan ? (
          <PlanBox>
            <PlanTitle>Pending Actions</PlanTitle>
            <PlanList>
              {pendingPlan.actions.map((action, index) => (
                <li key={`${action.action_type}-${index}`}>
                  {formatAction(action.action_type, action.params)}
                </li>
              ))}
            </PlanList>
            <ActionRow>
              <Button type="button" onClick={() => void confirmPlan()} disabled={isApplying}>
                {isApplying ? 'Applying…' : 'Confirm'}
              </Button>
              <DangerButton type="button" onClick={cancelPlan} disabled={isApplying}>
                Cancel
              </DangerButton>
            </ActionRow>
          </PlanBox>
        ) : null}

        <Form
          onSubmit={async (event) => {
            event.preventDefault();
            await submit();
          }}
        >
          <Input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={props.placeholder}
            onKeyDown={async (event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                await submit();
              }
            }}
          />
          <ActionRow>
            <Button type="submit" disabled={isSending || isApplying}>
              {isSending ? 'Planning…' : 'Send'}
            </Button>
          </ActionRow>
        </Form>
      </Body>
    </Panel>
  );
}
