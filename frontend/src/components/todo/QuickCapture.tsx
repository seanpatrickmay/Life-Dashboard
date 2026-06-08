import { useState, useRef } from 'react';
import styled from 'styled-components';
import { reducedMotion } from '../../styles/animations';
import { useProjectBoard } from '../../hooks/useProjectBoard';
import { useTodos } from '../../hooks/useTodos';
import { pixelPanel } from '../../theme/surfaces';

// ── Styled components ─────────────────────────────────────────────────────────

const Row = styled.div`
  ${pixelPanel}
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
`;

const TaskInput = styled.input`
  flex: 1;
  min-width: 0;
  min-height: 44px;
  box-sizing: border-box;
  background: transparent;
  border: none;
  outline: none;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.88rem;
  padding: 0 4px;

  &::placeholder {
    color: ${({ theme }) => theme.colors.textSecondary};
    opacity: 0.7;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
    border-radius: 4px;
  }
`;

const ProjectSelect = styled.select`
  min-height: 44px;
  box-sizing: border-box;
  padding: 0 28px 0 8px;
  border-radius: 8px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textSecondary};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.78rem;
  cursor: pointer;
  max-width: 130px;
  appearance: none;
  -webkit-appearance: none;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const AddButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid ${({ theme }) => theme.colors.accent}55;
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.accent};
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  ${reducedMotion}
  flex-shrink: 0;

  &:hover:not(:disabled) {
    background: ${({ theme }) => theme.colors.overlayHover};
    border-color: ${({ theme }) => theme.colors.accent}99;
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const ErrorHint = styled.span`
  display: block;
  margin-top: 4px;
  padding: 0 10px;
  font-size: 0.74rem;
  color: ${({ theme }) => theme.colors.danger};
  letter-spacing: 0.02em;
`;

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
`;

// ── Visually-hidden label helper ──────────────────────────────────────────────

const VisuallyHidden = styled.label`
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
`;

// ── Component ─────────────────────────────────────────────────────────────────

export function QuickCapture() {
  const [text, setText] = useState('');
  // 'inbox' | stringified project id
  const [projectValue, setProjectValue] = useState<string>('inbox');
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  const { boardQuery, createTodo: createBoardTodo } = useProjectBoard();
  const { createTodo: createInboxTodo } = useTodos();

  const projects = boardQuery.data?.projects ?? [];

  const inputId = 'quick-capture-input';
  const selectId = 'quick-capture-project';

  async function handleSubmit() {
    const trimmed = text.trim();
    if (!trimmed) return;

    setIsPending(true);
    setError(null);

    try {
      if (projectValue === 'inbox') {
        await createInboxTodo({ text: trimmed });
      } else {
        const projectId = parseInt(projectValue, 10);
        await createBoardTodo({ text: trimmed, project_id: projectId });
      }
      setText('');
      // Keep selected project intact so the user can batch-add to the same project
    } catch {
      setError('Failed to add task — please try again.');
    } finally {
      setIsPending(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      void handleSubmit();
    }
  }

  return (
    <Wrapper>
      <VisuallyHidden htmlFor={inputId}>Add a task</VisuallyHidden>
      <Row>
        <TaskInput
          ref={inputRef}
          id={inputId}
          aria-label="Add a task"
          placeholder="＋ Add a task…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isPending}
          autoComplete="off"
        />

        <VisuallyHidden htmlFor={selectId}>Project</VisuallyHidden>
        <ProjectSelect
          id={selectId}
          aria-label="Project"
          value={projectValue}
          onChange={(e) => setProjectValue(e.target.value)}
          disabled={isPending}
        >
          <option value="inbox">Inbox</option>
          {projects.map((p) => (
            <option key={p.id} value={String(p.id)}>
              {p.display_name ?? p.name}
            </option>
          ))}
        </ProjectSelect>

        <AddButton
          type="button"
          aria-label="Add task"
          onClick={() => void handleSubmit()}
          disabled={isPending}
        >
          ＋
        </AddButton>
      </Row>

      {error && <ErrorHint role="alert">{error}</ErrorHint>}
    </Wrapper>
  );
}
