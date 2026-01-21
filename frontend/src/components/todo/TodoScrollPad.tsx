import { useMemo, useState } from 'react';
import styled from 'styled-components';
import { useTodos } from '../../hooks/useTodos';
import type { TodoItem } from '../../services/api';

const ScrollShell = styled.div`
  position: relative;
  padding: 12px 16px 16px;
  border-radius: 20px;
  background: radial-gradient(circle at 0 0, rgba(255, 255, 255, 0.2), transparent 55%),
    radial-gradient(circle at 100% 0, rgba(248, 225, 176, 0.3), transparent 60%),
    linear-gradient(180deg, rgba(248, 237, 212, 0.96), rgba(235, 215, 184, 0.96));
  box-shadow: 0 10px 26px rgba(11, 18, 32, 0.55);
  color: #2b1b13;
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
  margin-bottom: 6px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.78rem;
`;

const Count = styled.span`
  font-size: 0.72rem;
  opacity: 0.7;
`;

const List = styled.ul`
  list-style: none;
  margin: 4px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const Row = styled.li<{ $completed: boolean; $overdue: boolean }>`
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 6px;
  align-items: center;
  padding: 4px 6px;
  border-radius: 8px;
  background: ${({ $overdue, $completed }) =>
    $completed
      ? 'rgba(0,0,0,0.04)'
      : $overdue
        ? 'rgba(141, 34, 36, 0.16)'
        : 'rgba(0,0,0,0.02)'};
  border: 1px solid
    ${({ $overdue, $completed }) =>
      $completed ? 'rgba(0,0,0,0.08)' : $overdue ? 'rgba(141, 34, 36, 0.4)' : 'rgba(0,0,0,0.12)'};
  opacity: ${({ $completed }) => ($completed ? 0.7 : 1)};
`;

const Checkbox = styled.button<{ $checked: boolean }>`
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.5);
  background: ${({ $checked }) =>
    $checked ? 'linear-gradient(135deg, #274457, #5e8a7a)' : 'rgba(255, 255, 255, 0.7)'};
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  color: #f6f0e8;
`;

const DeleteButton = styled.button`
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 0.8rem;
  color: rgba(86, 31, 24, 0.85);
  padding: 2px 4px;
`;

const NameBox = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
`;

const TextField = styled.textarea<{ $overdue: boolean; $completed: boolean }>`
  width: 100%;
  border: none;
  background: transparent;
  font-size: 0.82rem;
  font-family: ${({ theme }) => theme.fonts.body};
  text-align: center;
  color: ${({ $completed }) => ($completed ? 'rgba(43,27,19,0.6)' : 'rgba(43,27,19,0.96)')};
  text-decoration: ${({ $completed }) => ($completed ? 'line-through' : 'none')};
  outline: none;
  resize: vertical;
  line-height: 1.25;
  padding: 0;
  overflow: auto;
`;

const Deadline = styled.span<{ $overdue: boolean }>`
  display: block;
  font-size: 0.72rem;
  margin-left: 24px;
  color: ${({ $overdue }) => ($overdue ? 'rgba(141, 34, 36, 0.98)' : 'rgba(43,27,19,0.7)')};
`;

const Empty = styled.p`
  margin: 4px 0 0;
  font-size: 0.78rem;
  opacity: 0.7;
`;

const ErrorText = styled.p`
  margin: 4px 0 0;
  font-size: 0.75rem;
  color: #8d2224;
`;

type Props = {
  estimateExtraHeight?: (count: number) => number;
};

export function TodoScrollPad(_props: Props) {
  const { todosQuery, updateTodo, deleteTodo } = useTodos();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');

  const items = todosQuery.data ?? [];

  const handleToggle = async (item: TodoItem) => {
    await updateTodo({ id: item.id, completed: !item.completed });
  };

  const handleDelete = async (id: number) => {
    await deleteTodo(id);
  };

  const startEdit = (item: TodoItem) => {
    setEditingId(item.id);
    setEditingText(item.text);
  };

  const commitEdit = async (item: TodoItem) => {
    const trimmed = editingText.trim();
    if (!trimmed || trimmed === item.text) {
      setEditingId(null);
      return;
    }
    await updateTodo({ id: item.id, text: trimmed });
    setEditingId(null);
  };

  const formatDeadline = (item: TodoItem) => {
    if (!item.deadline_utc) return '';
    const local = new Date(item.deadline_utc);
    return local.toLocaleString();
  };

  const activeCount = useMemo(() => items.filter((item) => !item.completed).length, [items]);

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
      <List>
        {items.map((item) => {
          const overdue = !item.completed && item.is_overdue;
          const deadlineLabel = formatDeadline(item);
          const isEditing = editingId === item.id;
          return (
            <Row key={item.id} $completed={item.completed} $overdue={overdue}>
              <Checkbox
                type="button"
                aria-label={item.completed ? 'Mark as not done' : 'Mark as done'}
                $checked={item.completed}
                onClick={() => handleToggle(item)}
              >
                {item.completed ? '✓' : ''}
              </Checkbox>
              <div>
                <NameBox>
                <TextField
                  $overdue={overdue}
                  $completed={item.completed}
                  value={isEditing ? editingText : item.text}
                  rows={2}
                  onFocus={() => startEdit(item)}
                  onChange={(event) => {
                    if (!isEditing) startEdit(item);
                    setEditingText(event.target.value);
                  }}
                  onBlur={() => commitEdit(item)}
                />
                </NameBox>
                {deadlineLabel && <Deadline $overdue={overdue}>{deadlineLabel}</Deadline>}
              </div>
              <DeleteButton
                type="button"
                aria-label="Delete to-do"
                onClick={() => handleDelete(item.id)}
              >
                ✕
              </DeleteButton>
            </Row>
          );
        })}
      </List>
    </ScrollShell>
  );
}
