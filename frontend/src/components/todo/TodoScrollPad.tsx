import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import styled from 'styled-components';
import { useTodos } from '../../hooks/useTodos';
import type { TodoItem, TimeHorizon } from '../../services/api';

const ScrollShell = styled.div`
  position: relative;
  padding: 10px 14px 12px;
  border-radius: 20px;
  background: ${({ theme }) => theme.colors.backgroundCard};
  box-shadow: 0 10px 26px rgba(11, 18, 32, 0.55);
  color: ${({ theme }) => theme.colors.textPrimary};
  overflow: visible;

  &::before,
  &::after {
    content: '';
    position: absolute;
    left: 8px;
    right: 8px;
    height: 10px;
    border-radius: 999px;
    background: radial-gradient(circle at 50% 0, rgba(121, 88, 62, 0.9), transparent 70%);
    opacity: 0.9;
  }

  &::before {
    top: -6px;
  }

  &::after {
    bottom: -8px;
    transform: scaleY(-1);
  }
`;

const ScrollHeading = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.78rem;
`;

const Count = styled.span`
  font-size: 0.72rem;
  opacity: 0.7;
`;

const SectionLabel = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 0.68rem;
  opacity: 0.55;
  margin-top: 8px;
  margin-bottom: 1px;
  padding-left: 2px;
`;

const List = styled.ul`
  list-style: none;
  margin: 2px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
`;

const Row = styled.li<{ $completed: boolean; $overdue: boolean }>`
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px;
  align-items: start;
  padding: 4px 6px;
  border-radius: 8px;
  background: ${({ $overdue, $completed, theme }) =>
    $completed
      ? theme.colors.surfaceInset
      : $overdue
        ? theme.colors.dangerSubtle
        : theme.colors.surfaceInset};
  border: 1px solid
    ${({ $overdue, $completed, theme }) =>
      $completed ? theme.colors.borderSubtle : $overdue ? theme.colors.danger : theme.colors.borderSubtle};
  opacity: ${({ $completed }) => ($completed ? 0.7 : 1)};
`;

/* Left column: checkbox + small action buttons stacked below */
const LeftColumn = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding-top: 1px;
`;

const Checkbox = styled.button<{ $checked: boolean }>`
  width: 22px;
  height: 22px;
  border-radius: 4px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ $checked, theme }) =>
    $checked ? theme.colors.accent : theme.colors.overlay};
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  flex-shrink: 0;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const SmallAction = styled.button`
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 0.6rem;
  line-height: 1;
  color: ${({ theme }) => theme.colors.textSecondary};
  opacity: 0.5;
  padding: 1px 2px;

  &:hover {
    opacity: 1;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 1px;
  }
`;

const TextField = styled.textarea<{ $overdue: boolean; $completed: boolean }>`
  width: 100%;
  border: none;
  background: transparent;
  font-size: 0.82rem;
  font-family: ${({ theme }) => theme.fonts.body};
  text-align: left;
  color: ${({ $completed, theme }) => ($completed ? theme.colors.textSecondary : theme.colors.textPrimary)};
  text-decoration: ${({ $completed }) => ($completed ? 'line-through' : 'none')};
  outline: none;
  resize: none;
  overflow: hidden;
  line-height: 1.3;
  padding: 0;

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Deadline = styled.span<{ $overdue: boolean }>`
  display: block;
  font-size: 0.68rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: ${({ $overdue, theme }) => ($overdue ? theme.colors.danger : theme.colors.textSecondary)};
  margin-top: 1px;
`;

const CompletionEditor = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 4px;
`;

const CompletionInput = styled.input`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 8px;
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textPrimary};
  font-size: 0.74rem;
  padding: 4px 6px;
`;

const CompletionApply = styled.button`
  border: none;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.accent};
  color: ${({ theme }) => theme.colors.textPrimary};
  cursor: pointer;
  font-size: 0.7rem;
  padding: 5px 9px;
`;

const CompletionCancel = styled.button`
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textSecondary};
  cursor: pointer;
  font-size: 0.7rem;
  padding: 5px 9px;
`;

const Empty = styled.p`
  margin: 4px 0 0;
  font-size: 0.78rem;
  opacity: 0.7;
`;

const ErrorText = styled.p`
  margin: 4px 0 0;
  font-size: 0.75rem;
  color: ${({ theme }) => theme.colors.danger};
`;

type Props = {
  estimateExtraHeight?: (count: number) => number;
};

const HORIZON_ORDER: TimeHorizon[] = ['this_week', 'this_month', 'this_year'];
const HORIZON_LABELS: Record<TimeHorizon, string> = {
  this_week: 'This Week',
  this_month: 'This Month',
  this_year: 'This Year',
};

function toLocalDateTimeInputValue(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function defaultHistoricalCompletionValue(item: TodoItem): string {
  return toLocalDateTimeInputValue(item.deadline_utc ?? item.created_at);
}

/* Auto-resize textarea to fit content */
function useAutoResize(value: string) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const resize = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = '0';
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [value, resize]);

  return { ref, onInput: resize };
}

function AutoTextField({
  value,
  onFocus,
  onChange,
  onBlur,
  $overdue,
  $completed,
}: {
  value: string;
  onFocus: () => void;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onBlur: () => void;
  $overdue: boolean;
  $completed: boolean;
}) {
  const { ref, onInput } = useAutoResize(value);
  return (
    <TextField
      ref={ref}
      $overdue={$overdue}
      $completed={$completed}
      value={value}
      rows={1}
      onFocus={onFocus}
      onChange={(e) => {
        onChange(e);
        onInput();
      }}
      onBlur={onBlur}
    />
  );
}

export function TodoScrollPad(_props: Props) {
  const { todosQuery, updateTodo, deleteTodo } = useTodos();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const [historyTodoId, setHistoryTodoId] = useState<number | null>(null);
  const [historyValue, setHistoryValue] = useState('');

  const items = todosQuery.data ?? [];

  const handleToggle = (item: TodoItem) => {
    if (historyTodoId === item.id) {
      setHistoryTodoId(null);
      setHistoryValue('');
    }
    updateTodo({ id: item.id, completed: !item.completed });
  };

  const handleDelete = async (id: number) => {
    await deleteTodo(id);
  };

  const startEdit = (item: TodoItem) => {
    setEditingId(item.id);
    setEditingText(item.text);
  };

  const commitEdit = (item: TodoItem) => {
    const trimmed = editingText.trim();
    if (!trimmed || trimmed === item.text) {
      setEditingId(null);
      return;
    }
    updateTodo({ id: item.id, text: trimmed });
    setEditingId(null);
  };

  const formatDeadline = (item: TodoItem) => {
    if (!item.deadline_utc) return '';
    const local = new Date(item.deadline_utc);
    return local.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const openHistoricalCompletion = (item: TodoItem) => {
    setHistoryTodoId(item.id);
    setHistoryValue(defaultHistoricalCompletionValue(item));
  };

  const closeHistoricalCompletion = () => {
    setHistoryTodoId(null);
    setHistoryValue('');
  };

  const applyHistoricalCompletion = (item: TodoItem) => {
    if (!historyValue) return;
    const completedAt = new Date(historyValue);
    if (Number.isNaN(completedAt.getTime())) return;
    updateTodo({
      id: item.id,
      completed: true,
      completed_at_utc: completedAt.toISOString()
    });
    closeHistoricalCompletion();
  };

  const activeCount = useMemo(() => items.filter((item) => !item.completed).length, [items]);

  const grouped = useMemo(() => {
    const groups: Record<TimeHorizon, TodoItem[]> = {
      this_week: [],
      this_month: [],
      this_year: [],
    };
    for (const item of items) {
      const horizon = item.time_horizon ?? 'this_week';
      (groups[horizon] ?? groups.this_week).push(item);
    }
    return groups;
  }, [items]);

  const renderItem = (item: TodoItem) => {
    const overdue = !item.completed && item.is_overdue;
    const deadlineLabel = formatDeadline(item);
    const isEditing = editingId === item.id;
    return (
      <Row key={item.id} $completed={item.completed} $overdue={overdue}>
        <LeftColumn>
          <Checkbox
            type="button"
            aria-label={item.completed ? 'Mark as not done' : 'Mark as done'}
            $checked={item.completed}
            onClick={() => handleToggle(item)}
          >
            {item.completed ? '✓' : ''}
          </Checkbox>
          {!item.completed && (
            <SmallAction
              type="button"
              aria-label="Mark completed on a chosen date"
              title="Done on…"
              onClick={() =>
                historyTodoId === item.id ? closeHistoricalCompletion() : openHistoricalCompletion(item)
              }
            >
              ▾
            </SmallAction>
          )}
          <SmallAction
            type="button"
            aria-label="Delete to-do"
            title="Delete"
            onClick={() => handleDelete(item.id)}
          >
            ✕
          </SmallAction>
        </LeftColumn>
        <div>
          <AutoTextField
            $overdue={overdue}
            $completed={item.completed}
            value={isEditing ? editingText : item.text}
            onFocus={() => startEdit(item)}
            onChange={(event) => {
              if (!isEditing) startEdit(item);
              setEditingText(event.target.value);
            }}
            onBlur={() => commitEdit(item)}
          />
          {deadlineLabel && <Deadline $overdue={overdue}>{deadlineLabel}</Deadline>}
          {historyTodoId === item.id && !item.completed ? (
            <CompletionEditor>
              <CompletionInput
                type="datetime-local"
                value={historyValue}
                onChange={(event) => setHistoryValue(event.target.value)}
              />
              <CompletionApply type="button" onClick={() => applyHistoricalCompletion(item)}>
                Save date
              </CompletionApply>
              <CompletionCancel type="button" onClick={closeHistoricalCompletion}>
                Cancel
              </CompletionCancel>
            </CompletionEditor>
          ) : null}
        </div>
      </Row>
    );
  };

  return (
    <ScrollShell>
      <ScrollHeading>
        <span data-halo="heading">Task list</span>
        <Count>{activeCount} open</Count>
      </ScrollHeading>
      {todosQuery.error && (
        <ErrorText data-halo="body">Could not load to-dos right now.</ErrorText>
      )}
      {items.length === 0 && !todosQuery.isLoading && (
        <Empty data-halo="body">Nothing here yet — add something on the left.</Empty>
      )}
      {HORIZON_ORDER.map((horizon) => {
        const sectionItems = grouped[horizon];
        if (sectionItems.length === 0) return null;
        return (
          <div key={horizon}>
            <SectionLabel>{HORIZON_LABELS[horizon]}</SectionLabel>
            <List>
              {sectionItems.map(renderItem)}
            </List>
          </div>
        );
      })}
    </ScrollShell>
  );
}
